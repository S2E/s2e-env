"""
Copyright (c) 2017 Cyberhaven
Copyright (c) 2017 Dependable Systems Laboratory, EPFL

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


import glob
import grp
import logging
import os
import pwd
import re
import socket
import time

from threading import Thread

import psutil
from psutil import NoSuchProcess

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

import sh
from sh import ErrorReturnCode

from s2e_env import CONSTANTS
from s2e_env.command import EnvCommand, CommandError
from s2e_env.utils import repos
from s2e_env.utils.images import ImageDownloader, get_image_templates, get_app_templates, get_all_images, \
                                 translate_image_name


logger = logging.getLogger('image_build')


def _get_user_groups(user_name):
    """
    Get a list of groups for the user ``user_name``.
    """
    groups = [g.gr_name for g in grp.getgrall() if user_name in g.gr_mem]
    gid = pwd.getpwnam(user_name).pw_gid
    groups.append(grp.getgrgid(gid).gr_name)

    return groups


def _get_user_name():
    """
    Get the current user.
    """
    return pwd.getpwuid(os.getuid())[0]


def _user_belongs_to(group_name):
    """
    Check that the current user belongs to the ``group_name`` group.
    """
    user_name = _get_user_name()
    groups = _get_user_groups(user_name)
    return group_name in groups


def _raise_group_error(group_name):
    raise CommandError('You must belong to the {0} group in order to build '
                       'images. Please run the following command, then logout '
                       'and login:\n\n'
                       '\tsudo usermod -a -G {0} $(whoami)'.format(group_name))


def _check_groups_docker():
    """
    Check that the current user belongs to the required groups to both run S2E and build S2E images.
    """
    if not _user_belongs_to('docker'):
        _raise_group_error('docker')


def _check_groups_kvm():
    """Being member of KVM is required only when using KVM to build images"""
    if not _user_belongs_to('libvirtd') and not _user_belongs_to('kvm'):
        _raise_group_error('kvm')


def _check_virtualbox():
    """
    Check if VirtualBox is running. VirtualBox conflicts with S2E's requirement for KVM, so VirtualBox must
    *not* be running together with S2E.
    """
    # Adapted from https://github.com/giampaolo/psutil/issues/132#issuecomment-44017679
    # to avoid race conditions
    for proc in psutil.process_iter():
        try:
            if proc.name() == 'VBoxHeadless':
                raise CommandError('S2E uses KVM to build images. VirtualBox '
                                   'is currently running, which is not '
                                   'compatible with KVM. Please close all '
                                   'VirtualBox VMs and try again.')
        except NoSuchProcess:
            pass


def _check_vmware():
    """
    Check if VMWare is running. VMware conflicts with S2E's requirement for KVM, so VMWare must
    *not* be running together with S2E.
    """
    for proc in psutil.process_iter():
        try:
            if proc.name() == 'vmware-vmx':
                raise CommandError('S2E uses KVM to build images. VMware '
                                   'is currently running, which is not '
                                   'compatible with KVM. Please close all '
                                   'VMware VMs and try again.')
        except NoSuchProcess:
            pass


def _check_kvm():
    """
    Check that the KVM interface exists. This is required by libs2e to communicate with QEMU.
    """
    if not os.path.exists(os.path.join(os.sep, 'dev', 'kvm')):
        raise CommandError('KVM interface not found - check that /dev/kvm '
                           'exists. Alternatively, you can disable KVM (-n '
                           'option) or download pre-built images (-d option)')


def _check_vmlinux():
    """
    Check that /boot/vmlinux* files are readable. This is important for guestfish.
    """
    try:
        for f in glob.glob(os.path.join(os.sep, 'boot', 'vmlinu*')):
            with open(f):
                pass
    except IOError:
        raise CommandError('Make sure that the kernels in /boot are readable. '
                           'This is required for guestfish. Please run the '
                           'following command:\n\n'
                           'sudo chmod ugo+r /boot/vmlinu*')


# pylint: disable=no-member
def _check_cow(image_dir):
    """
    Check that the file system that stores guest images supports copy-on-write.
    """
    try:
        src = f'{image_dir}/.cowcheck'
        dst = f'{image_dir}/.cowcheck1'
        sh.touch(src)
        sh.cp('--reflink=always', src, dst)
        return True
    except Exception:
        warn_msg = f"""
        Copy-on-write check failed.
        The file system where images are stored ({image_dir}) does not support copy-on-write.
        It is recommended to use an XFS or BTRFS file system with copy-on-write enabled as a storage
        location for S2E images, as this can save up to 60% of disk space. The building process checkpoints
        intermediate build steps with cp --reflink=auto to make use of copy-on-write if it is available.

        How to upgrade:
            1. Create an XFS or BTRFS partition large enough to store the images that you need (~300 GB for all images).
               Make sure you use reflink=1 to enable copy-on-write when running mkfs.xfs.
            2. Create a directory for guest images on that partition (e.g., /mnt/disk1/images)
            3. Delete the "images" folder in your S2E environment
            4. Create in your S2E environment a symbolic link called "images" to the directory you created in step 2
        """
        logger.warning(re.sub(r'^ {8}', '', warn_msg, flags=re.MULTILINE))
        return False
    finally:
        sh.rm('-f', src)
        sh.rm('-f', dst)


def _raise_invalid_image(image_name):
    raise CommandError('Invalid image name: %s. Run ``s2e image_build`` '
                       'to list available images' % image_name)


def _get_base_image_and_app(image_name):
    x = image_name.split('/')
    if len(x) == 1:
        return x[0], None
    if len(x) == 2:
        return x
    raise CommandError(f'Invalid image name {image_name}')


def _has_app_image(image_names):
    for name in image_names:
        if '/' in name:
            return True
    return False


def _check_product_keys(image_descriptors, image_names):
    missing_keys = []

    for image_name in image_names:
        image = image_descriptors[image_name]

        if 'product_key' in image:
            if not image['product_key']:
                missing_keys.append(image_name)

        ios = image_descriptors[image_name].get('os', {})
        if 'product_key' in ios:
            if not ios['product_key']:
                missing_keys.append(image_name)

    if missing_keys:
        logger.error('The following images require a product key:')
        for image in missing_keys:
            logger.error(' * %s', image)

        raise CommandError('Please update images.json and/or apps.json.')


def _check_iso(templates, app_templates, iso_dir, image_names):
    for image_name in image_names:
        base_image, app_name = _get_base_image_and_app(image_name)

        descriptors = [templates[base_image]]
        if app_name:
            descriptors.append(app_templates[app_name])

        for desc in descriptors:
            iso = desc.get('iso', {})
            if iso.get('url', ''):
                continue

            name = iso.get('name', '')
            if not name:
                continue

            if not iso_dir:
                raise CommandError(
                    'Please use the --iso-dir option to specify the path '
                    'to a folder that contains %s' % name
                )

            path = os.path.join(iso_dir, name)
            if not os.path.exists(path):
                raise CommandError('The image %s requires %s, which could not be '
                                   'found' % (image_name, path))


def _is_port_available(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        s.bind(("127.0.0.1", port))
        return True
    except socket.error:
        return False
    finally:
        s.close()


def _start_ftp_server(image_path, port):
    authorizer = DummyAuthorizer()
    authorizer.add_anonymous(image_path, perm='elradfmwMT')
    handler = FTPHandler
    handler.authorizer = authorizer
    handler.masquerade_address = '10.0.2.2'
    # QEMU slirp won't let the guest reconnect if timeout happens, so we disable it
    handler.timeout = None

    server = FTPServer(("127.0.0.1", port), handler)

    thread = Thread(target=_run_ftp_server, args=[server])
    thread.daemon = True
    thread.start()
    time.sleep(1)

    return server


def _run_ftp_server(server):
    try:
        server.serve_forever()
    finally:
        logger.info('FTP server terminated')
        server.close_all()


def _get_archive_rules(image_path, rule_names):
    if _has_app_image(rule_names):
        raise CommandError('Building archives of app images is not supported yet')

    archive_rules = []
    for r in rule_names:
        archive_rules.append(os.path.join(image_path, '%s.tar.xz' % r))

    logger.info('The following archives will be built:')
    for a in archive_rules:
        logger.info(' * %s', a)

    return archive_rules


def _download_images(image_path, image_names, templates):
    if _has_app_image(image_names):
        raise CommandError('Downloading of app images is not supported yet')

    image_downloader = ImageDownloader(templates)
    image_downloader.download_images(image_names, image_path)

    logger.info('Successfully downloaded images: %s', ', '.join(image_names))


class Command(EnvCommand):
    """
    Builds an image.
    """

    help = 'Build an image.'

    def __init__(self):
        super(Command, self).__init__()

        self._headless = True
        self._use_kvm = True
        self._num_cores = 1
        self._has_cow = False

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('name',
                            help='The name of the image to build. If empty,'
                                 ' shows available images', nargs='*')
        parser.add_argument('-g', '--gui', action='store_true',
                            help='Display QEMU GUI during image build')
        parser.add_argument('-c', '--cores', required=False, default=2,
                            type=int,
                            help='The number of cores used when building the '
                                 'VM image. Defaults to 2')
        parser.add_argument('-x', '--clean', action='store_true',
                            help='Deletes all images and rebuild them from '
                                 'scratch')
        parser.add_argument('-a', '--archive', action='store_true',
                            help='Creates an archive for the specified image')
        parser.add_argument('-p', '--ftp-port', required=False, default=15468, type=int,
                            help='Port for the internal FTP server to receive files from guest VMs during build')
        parser.add_argument('-d', '--download', action='store_true',
                            help='Download image from the repository instead '
                                 'of building it')
        parser.add_argument('-i', '--iso-dir',
                            help='Path to folder that stores ISO files of Windows images')
        parser.add_argument('-n', '--no-kvm', action='store_true',
                            help='Disable KVM during image build')

    def handle(self, *args, **options):
        # If DISPLAY is missing, don't use headless mode
        if options['gui']:
            self._headless = False

        # If KVM has been explicitly disabled, don't use it during the build
        if options['no_kvm']:
            self._use_kvm = False

        self._num_cores = options['cores']

        # The path could have been deleted by a previous clean
        if not os.path.exists(self.image_path()):
            os.makedirs(self.image_path())

        img_build_dir = self.source_path(CONSTANTS['repos']['images']['build'])

        if options['clean']:
            self._invoke_make(img_build_dir, ['clean'])
            return

        image_names = options['name']
        templates = get_image_templates(img_build_dir)
        app_templates = get_app_templates(img_build_dir)
        images, image_groups, image_descriptors = get_all_images(templates, app_templates)

        if not image_names:
            self._print_image_list(images, image_groups, image_descriptors)
            print('\nRun ``s2e image_build <name>`` to build an image. '
                  'Note that you must run ``s2e build`` **before** building '
                  'an image')
            return

        image_names = translate_image_name(images, image_groups, image_names)
        logger.info('The following images will be built:')
        for image in image_names:
            logger.info(' * %s', image)

        if options['download']:
            _download_images(self.image_path(), image_names, templates)
            return

        rule_names = image_names

        if options['archive']:
            rule_names = _get_archive_rules(self.image_path(), image_names)

        iso_dir = os.path.abspath(options['iso_dir']) if options['iso_dir'] else None

        # Check for optional product keys and iso directories.
        # These may or may not be required, depending on the set of images.
        _check_product_keys(image_descriptors, image_names)
        _check_iso(templates, app_templates, iso_dir, image_names)

        if self._use_kvm:
            _check_kvm()
            _check_groups_kvm()

        _check_groups_docker()
        _check_vmlinux()

        self._has_cow = _check_cow(self.image_path())

        if self._use_kvm:
            _check_virtualbox()
            _check_vmware()

        if not _is_port_available(options['ftp_port']):
            raise CommandError(f'localhost:{options["ftp_port"]} is not available. Check that the port is free or '
                               'specify a port with --ftp-port')

        # Clone kernel if needed.
        # This is necessary if the s2e env has been initialized with -b flag.
        self._clone_kernel()

        server = _start_ftp_server(self.image_path(), options['ftp_port'])

        self._invoke_make(img_build_dir, rule_names, options['ftp_port'], iso_dir)

        logger.success('Built image(s) \'%s\'', ' '.join(image_names))

        server.close_all()

    def _invoke_make(self, img_build_dir, rule_names, ftp_port=0, iso_dir=''):
        env = os.environ.copy()
        env['S2E_INSTALL_ROOT'] = self.install_path()
        env['S2E_LINUX_KERNELS_ROOT'] = \
            self.source_path(CONSTANTS['repos']['images']['linux'])
        env['OUTDIR'] = self.image_path()
        env['QEMU_FTP_PORT'] = str(ftp_port)
        env['ISODIR'] = iso_dir if iso_dir else ''
        env['DEBUG_INTERMEDIATE_RULES'] = '1' if self._has_cow else '0'

        logger.debug('Invoking makefile with:')
        logger.debug('export S2E_INSTALL_ROOT=%s', env['S2E_INSTALL_ROOT'])
        logger.debug('export S2E_LINUX_KERNELS_ROOT=%s', env['S2E_LINUX_KERNELS_ROOT'])
        logger.debug('export OUTDIR=%s', env['OUTDIR'])
        logger.debug('export ISODIR=%s', env.get('ISODIR', ''))
        logger.debug('export DEBUG_INTERMEDIATE_RULES=%s', env.get('DEBUG_INTERMEDIATE_RULES', ''))

        if self._headless:
            logger.warning('Image creation will run in headless mode. '
                           'Use --gui to see graphic output for debugging')
        else:
            env['GRAPHICS'] = ''

        if not self._use_kvm:
            env['QEMU_KVM'] = ''
            logger.warning('Image build without KVM. This will be slow')

        try:
            make = sh.Command('make').bake(file=os.path.join(img_build_dir,
                                                             'Makefile'),
                                           directory=self.image_path(),
                                           _env=env, _fg=True)

            make_image = make.bake(j=self._num_cores, r=True, warn_undefined_variables=True)
            make_image(sorted(rule_names))
        except ErrorReturnCode as e:
            raise CommandError(e)

    def _clone_kernel(self):
        kernels_root = self.source_path(CONSTANTS['repos']['images']['linux'])
        if os.path.exists(kernels_root):
            logger.info('Kernel repository already exists in %s', kernels_root)
            return

        logger.info('Cloning kernels repository to %s', kernels_root)

        kernels_repo = CONSTANTS['repos']['images']['linux']
        repos.git_clone_to_source(self.env_path(), kernels_repo)

    def _print_image_list(self, images, image_groups, image_descriptors):
        img_build_dir = self.source_path(CONSTANTS['repos']['images']['build'])
        templates = get_image_templates(img_build_dir)
        if not templates:
            raise CommandError('No images available to build. Make sure that '
                               '%s exists and is valid' %
                               os.path.join(img_build_dir, 'images.json'))

        def get_max_len(lst):
            ret = 0
            for item in lst:
                if len(item) > ret:
                    ret = len(item)
            return ret

        print('Available image groups:')
        max_group_len = get_max_len(image_groups)
        for group in image_groups:
            print(f' * {group:{max_group_len}} - Build {group} images')

        print('\nAvailable images:')
        max_image_len = get_max_len(images)
        for image in sorted(images):
            print(f' * {image:{max_image_len}} - {image_descriptors[image]["name"]}')

    def _print_apps_list(self):
        img_build_dir = self.source_path(CONSTANTS['repos']['images']['build'])
        app_templates = get_app_templates(img_build_dir)
        if not app_templates:
            raise CommandError('No apps available to build. Make sure that '
                               '%s exists and is valid' %
                               os.path.join(img_build_dir, 'apps.json'))

        print('Available applications:')
        for app_template, desc in sorted(app_templates.items()):
            for base_image in desc['base_images']:
                print(' * %s/%s - %s' % (base_image, app_template, desc['name']))

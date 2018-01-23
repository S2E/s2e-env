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


from __future__ import print_function

import glob
import grp
import json
import logging
import os
import pwd
import sys

import psutil
from psutil import NoSuchProcess
import sh
from sh import ErrorReturnCode

from s2e_env import CONSTANTS
from s2e_env.command import EnvCommand, CommandError
from s2e_env.utils import repos
from s2e_env.utils.image_download import ImageDownloader


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


def _check_groups():
    """
    Check that the current user belongs to the required groups to both run S2E
    and build S2E images.
    """
    if not _user_belongs_to('docker'):
        _raise_group_error('docker')

    if not _user_belongs_to('libvirtd') and not _user_belongs_to('kvm'):
        _raise_group_error('kvm')


def _check_virtualbox():
    """
    Check if VirtualBox is running.

    VirtualBox conflicts with S2E's requirement for KVM, so VirtualBox must
    *not* be running together with S2E.
    """
    # Adapted from https://github.com/giampaolo/psutil/issues/132#issuecomment-44017679
    # to avoid race conditions
    for proc in psutil.process_iter():
        try:
            if proc.name == 'VBoxHeadless':
                raise CommandError('S2E uses KVM to build images. VirtualBox '
                                   'is currently running, which is not '
                                   'compatible with KVM. Please close all '
                                   'VirtualBox VMs and try again')
        except NoSuchProcess:
            pass


def _check_kvm():
    """
    Check that the KVM interface exists.

    This is required by libs2e to communicate with QEMU.
    """
    if not os.path.exists(os.path.join(os.sep, 'dev', 'kvm')):
        raise CommandError('KVM interface not found - check that /dev/kvm '
                           'exists. Alternatively, you can disable KVM (-n '
                           'option) or download pre-built images (-d option)')


def _check_vmlinux():
    """
    Check that /boot/vmlinux* files are readable. This is important for
    guestfish.
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


def _validate_version(descriptor, filename):
    version = descriptor.get('version')
    required_version = CONSTANTS['required_versions']['guest_images']
    if version != required_version:
        raise CommandError('Need version %s for %s. Make sure that you have '
                           'the correct revision of the guest-images '
                           'repository' % (required_version, filename))


def get_image_templates(img_build_dir):
    images = os.path.join(img_build_dir, 'images.json')
    try:
        with open(images, 'r') as f:
            template_json = json.load(f)
    except:
        raise CommandError('Could not parse %s. Something is wrong with the '
                           'environment' % images)

    _validate_version(template_json, images)
    return template_json['images']


def get_image_descriptor(image_dir):
    """
    Load the image JSON descriptor.

    Args:
        image_dir: directory containing the built image.
    """
    img_json_path = os.path.join(image_dir, 'image.json')

    try:
        with open(img_json_path, 'r') as f:
            ret = json.load(f)
            _validate_version(ret, img_json_path)
            ret['path'] = os.path.join(image_dir, 'image.raw.s2e')

            return ret
    except Exception:
        raise CommandError('Unable to open image description %s. Check that '
                           'the image exists, was built, or downloaded' % img_json_path)


def _check_core_num(value):
    """
    Ensure that the number of CPU cores is sensible.
    """
    if value <= 0 or value > 10:
        logger.warning('The specified number of cores seems high. Less than '
                       '10 is recommended for best image building performance')


def _translate_image_name(templates, image_name):
    """
    Translates a set of user-friendly image names into a set of actual image
    names that can be sent to the makefile. For example, "all" will be
    translated to the set of all images, while "windows" and "linux" will be
    translated to the appropriate subset of Windows or Linux images.
    """
    ret = []
    if image_name == 'all':
        ret = templates.keys()
    elif image_name in Command.image_groups:
        for k, v in templates.iteritems():
            if v['image_group'] == image_name:
                ret.append(k)
    elif image_name in templates.keys():
        ret = [image_name]
    else:
        raise CommandError('Invalid image name: %s. Run ``s2e image_build`` '
                           'to list available images' % image_name)

    return ret


def _check_product_keys(templates, image_names):
    for image in image_names:
        ios = templates[image].get('os', {})
        if not 'product_key' in ios:
            continue

        if not ios['product_key']:
            raise CommandError('Image %s requires a product key. '
                               'Please update images.json.' % image)


def _check_iso(templates, iso_dir, image_names):
    for image in image_names:
        iso = templates[image].get('iso', {})
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
                               'found' % (image, path))


class Command(EnvCommand):
    """
    Builds an image.
    """

    help = 'Build an image.'
    image_groups = ('windows', 'linux')
    generic_rules = ('all',) + image_groups

    def __init__(self):
        super(Command, self).__init__()

        self._headless = True
        self._use_kvm = True

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('name',
                            help='The name of the image to build. If empty,'
                                 ' shows available images', nargs='?')
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

        num_cores = options['cores']
        _check_core_num(num_cores)

        # The path could have been deleted by a previous clean
        if not os.path.exists(self.image_path()):
            os.makedirs(self.image_path())

        img_build_dir = self.source_path(CONSTANTS['repos']['images']['build'])

        if options['clean']:
            self._invoke_make(img_build_dir, ['clean'], num_cores)
            return

        image_name = options['name']
        if not image_name:
            self._print_image_list()
            return

        templates = get_image_templates(img_build_dir)

        image_names = _translate_image_name(templates, image_name)
        logger.info('The following images will be built:')
        for image in image_names:
            logger.info(' * %s', image)

        if options['download']:
            image_downloader = ImageDownloader(templates)
            image_downloader.download_images(image_names, self.image_path())

            logger.info('Successfully downloaded images: %s', ', '.join(image_names))
            return

        rule_names = image_names

        if options['archive']:
            archive_rules = []
            for r in rule_names:
                archive_rules.append(os.path.join(self.image_path(), '%s.tar.xz' % r))

            rule_names = archive_rules
            logger.info('The following archives will be built:')
            for a in archive_rules:
                logger.info(' * %s', a)

        # Check for optional product keys and iso directories.
        # These may or may not be required, depending on the set of images.
        _check_product_keys(templates, image_names)
        _check_iso(templates, options['iso_dir'], image_names)

        if self._use_kvm:
            _check_kvm()

        _check_groups()
        _check_vmlinux()
        _check_virtualbox()

        # Clone kernel if needed.
        # This is necessary if the s2e env has been initialized with -b flag.
        self._clone_kernel()

        self._invoke_make(img_build_dir, rule_names, num_cores, options['iso_dir'])

        logger.success('Built image \'%s\'', image_name)

    def _invoke_make(self, img_build_dir, rule_names, num_cores, iso_dir=''):
        env = os.environ.copy()
        env['S2E_INSTALL_ROOT'] = self.install_path()
        env['S2E_LINUX_KERNELS_ROOT'] = \
            self.source_path(CONSTANTS['repos']['images']['linux'])
        env['OUTDIR'] = self.image_path()

        if iso_dir:
            env['ISODIR'] = iso_dir

        logger.debug('Invoking makefile with:')
        logger.debug('export S2E_INSTALL_ROOT=%s', env['S2E_INSTALL_ROOT'])
        logger.debug('export S2E_LINUX_KERNELS_ROOT=%s', env['S2E_LINUX_KERNELS_ROOT'])
        logger.debug('export OUTDIR=%s', env['OUTDIR'])
        logger.debug('export ISODIR=%s', env.get('ISODIR', ''))

        if not self._headless:
            env['GRAPHICS'] = ''
        else:
            logger.warn('Image creation will run in headless mode. '
                        'Use --gui to see graphic output for debugging')

        if not self._use_kvm:
            env['QEMU_KVM'] = ''
            logger.warn('Image build without KVM. This will be slow')

        try:
            make = sh.Command('make').bake(file=os.path.join(img_build_dir,
                                                             'Makefile'),
                                           directory=self.image_path(),
                                           _out=sys.stdout, _err=sys.stderr,
                                           _env=env, _fg=True)

            make_image = make.bake(j=num_cores)
            make_image(rule_names)
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

    def _print_image_list(self):
        img_build_dir = self.source_path(CONSTANTS['repos']['images']['build'])
        templates = get_image_templates(img_build_dir)

        if not templates:
            raise CommandError('No images available to build. Make sure that '
                               '%s exists and is valid' %
                               os.path.join(img_build_dir, 'images.json'))

        print('Available images:')
        print(' * all - Build all images')
        print(' * linux - Build all Linux images')
        print(' * windows - Build all Windows images')
        print('')
        for template, desc in sorted(templates.iteritems()):
            print(' * %s - %s' % (template, desc['name']))

        print('\nRun ``s2e image_build <name>`` to build an image. '
              'Note that you must run ``s2e build`` **before** building '
              'an image')

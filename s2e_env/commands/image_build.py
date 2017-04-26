"""
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
from sh import tar, ErrorReturnCode

from s2e_env import CONSTANTS
from s2e_env.command import EnvCommand, CommandError
from s2e_env.utils import google, repos


logger = logging.getLogger('image_build')


def _get_user_groups(user_name):
    groups = [g.gr_name for g in grp.getgrall() if user_name in g.gr_mem]
    gid = pwd.getpwnam(user_name).pw_gid
    groups.append(grp.getgrgid(gid).gr_name)
    return groups


def _get_user_name():
    return pwd.getpwuid(os.getuid())[0]


def _user_belongs_to(group_name):
    user_name = _get_user_name()
    groups = _get_user_groups(user_name)
    return group_name in groups


def _raise_group_error(group_name):
    raise CommandError('You must belong to the {0} group in order to build '
                       'images. Please run the following command, then logout '
                       'and login:\n\n'
                       '\tsudo usermod -a -G {0} $(whoami)'.format(group_name))


def _check_groups():
    if not _user_belongs_to('docker'):
        _raise_group_error('docker')

    if not _user_belongs_to('libvirtd') and not _user_belongs_to('kvm'):
        _raise_group_error('kvm')


def _check_virtualbox():
    # Adapted from https://github.com/giampaolo/psutil/issues/132#issuecomment-44017679
    # to avoid race coditions
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
    if not os.path.exists(os.path.join(os.sep, 'dev', 'kvm')):
        raise CommandError('KVM is required to build images. Check that '
                           '/dev/kvm exists. Alternatively, you can also '
                           'download pre-built images (-d option).')


def _check_vmlinux():
    """
    Check that /boot/vmlinux* files are readable.
    This is important for guestfish.
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


def get_image_templates(img_build_dir):
    images = os.path.join(img_build_dir, 'images.json')
    try:
        with open(images, 'r') as f:
            template_json = json.load(f)
            return template_json['images']
    except:
        raise CommandError('Could not parse %s. Something is wrong with the '
                           'environment' % images)


def _download(url, path):
    """
    Download a file from the Google drive and save it at the given ``path``.
    """
    logger.info('Downloading %s', url)
    google.download(url, path)


def _decompress(path):
    """
    Decompress a .tar.xz file at the given path.

    The decompressed data will be located in the same directory as ``path``.
    """
    logger.info('Decompressing %s', path)
    try:
        tar(extract=True, xz=True, verbose=True, file=path,
            directory=os.path.dirname(path), _fg=True, _out=sys.stdout,
            _err=sys.stderr)
    except ErrorReturnCode as e:
        raise CommandError(e)


class ImageDownloaderMixin(object):
    def download_images(self, image_name=None):
        img_build_dir = self.source_path(CONSTANTS['repos']['images']['build'])
        templates = get_image_templates(img_build_dir)

        if image_name:
            images = [image_name]
        else:
            images = templates.keys()

        for image in images:
            self._download_image(templates, image)

    def _download_image(self, templates, image):
        dest_file = self.image_path('%s.tar.xz' % image)
        _download(templates[image]['url'], dest_file)
        _decompress(dest_file)


def _check_ram_size(value):
    """
    Ensure that the amount of RAM is sensible.
    """
    if value <= 0 or value > 2 * 1024:
        logger.warning('The specified memory size for the image looks too '
                       'high. Less than 2GB is recommended for best '
                       'performance')

def _check_core_num(value):
    """
    Ensure that the number of CPU cores is sensible.
    """
    if value <= 0 or value > 10:
        logger.warning('The specified number of cores seems high. Less than '
                       '10 is recommended for best image building performance')

class Command(EnvCommand, ImageDownloaderMixin):
    """
    Builds an image.
    """

    help = 'Build an image.'

    def __init__(self):
        super(Command, self).__init__()

        # If we are running without an X session, run QEMU in headless mode
        self._headless = os.environ.get('DISPLAY') is None

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('name',
                            help='The name of the image to build. If empty,'
                                 ' shows available images', nargs='?')
        parser.add_argument('-g', '--headless', action='store_true',
                            help='Build the image in headless mode (i.e. '
                                 'without a GUI)')
        parser.add_argument('-m', '--memory', required=False, default=256,
                            type=int,
                            help='Amount of RAM allocated to the image. '
                                 'Defaults to 256 MB')
        parser.add_argument('-c', '--cores', required=False, default=2,
                            type=int,
                            help='The number of cores used when building the '
                                 'VM image. Defaults to 2')
        parser.add_argument('-x', '--clean', action='store_true',
                            help='Deletes all images and rebuild them from '
                                 'scratch')
        parser.add_argument('-a', '--archive', action='store_true',
                            help='Creates an archive of every supported image')
        parser.add_argument('-d', '--download', action='store_true',
                            help='Download image from the repository instead '
                                 'of building it')

    def handle(self, *args, **options):
        # If DISPLAY is missing, don't use headless mode
        if options['headless']:
            self._headless = True

        image_name = options['name']
        if not image_name:
            self._print_image_list()
            return

        memory = options['memory']
        _check_ram_size(memory)

        num_cores = options['cores']
        _check_core_num(num_cores)

        # The path could have been deleted by a previous clean
        if not os.path.exists(self.image_path()):
            os.makedirs(self.image_path())

        img_build_dir = self.source_path(CONSTANTS['repos']['images']['build'])
        templates = get_image_templates(img_build_dir)

        if image_name != 'all' and image_name not in templates:
            raise CommandError('Invalid image image_name %s' % image_name)

        if options['download']:
            if image_name == 'all':
                self.download_images()
            else:
                self.download_images(image_name)
            return 'Successfully downloaded image %s' % image_name

        _check_kvm()
        _check_groups()
        _check_vmlinux()
        _check_virtualbox()

        rule_name = image_name

        if options['archive']:
            rule_name = 'archive'
            if image_name != 'all':
                rule_name = os.path.join(self.image_path(),
                                         '%s.tar.xz' % image_name)

        # Clone kernel if needed.
        # This is necessary if the s2e env has been initialized with -b flag.
        self._clone_kernel()

        env = os.environ.copy()

        env['S2E_INSTALL_ROOT'] = self.install_path()
        env['S2E_LINUX_KERNELS_ROOT'] = \
            self.source_path(CONSTANTS['repos']['images']['linux'])
        env['OUTPUT_DIR'] = self.image_path()
        env['SNAPSHOT_MEMORY'] = str(memory)

        if not self._headless:
            env['GRAPHICS'] = ''

        try:
            make = sh.Command('make').bake(file=os.path.join(img_build_dir,
                                                             'Makefile'),
                                           directory=self.image_path(),
                                           _out=sys.stdout, _err=sys.stderr,
                                           _env=env, _fg=True)
            if options['clean']:
                make('clean')

            make_image = make.bake(j=num_cores)
            make_image(rule_name)
        except ErrorReturnCode as e:
            raise CommandError(e)

        return 'Built image \'%s\'' % image_name

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
        for template, desc in sorted(templates.iteritems()):
            print(' * %s - %s' % (template, desc['name']))
        print('\nRun ``s2e image_build <name>`` to build an image. '
              'Note that you must run ``s2e build`` **before** building '
              'an image')

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
import os
import pwd
import sh
import subprocess
import sys

from sh import ErrorReturnCode
from s2e_env import CONSTANTS
from s2e_env.command import EnvCommand, CommandError
import s2e_env.utils.google


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


def _print_group_error(group_name):
    print('You must belong to %s in order to build images.' % group_name)
    print('Please run the following command, then logout and login:')
    print('')
    print('   sudo usermod -a -G %s $(whoami)' % group_name)


def _check_groups():
    if not _user_belongs_to('docker'):
        _print_group_error('docker')
        raise CommandError()

    if not _user_belongs_to('libvirtd') and not _user_belongs_to('kvm'):
        _print_group_error('kvm')
        raise CommandError()


def _check_vmlinux():
    """
    Check that /boot/vmlinux* files are readable.
    This is important for guestfish.
    """
    try:
        for f in glob.glob("/boot/vmli*"):
            with open(f):
                pass
    except IOError:
        raise CommandError('Make sure that kernels in /boot are readable. This is required for guestfish.')


def get_image_templates(img_build_dir):
    images = os.path.join(img_build_dir, "images.json")
    with open(images, 'r') as f:
        template_json = json.load(f)
        return template_json['images']


class Command(EnvCommand):
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
        parser.add_argument('-c', '--num-cores', required=False, default=2,
                            type=int,
                            help='The number of cores used when building the '
                                 'VM image. Defaults to 2')
        parser.add_argument('-x', '--clean', action='store_true',
                            help='Deletes all images and rebuilds them from scratch')
        parser.add_argument('-a', '--archive', action='store_true',
                            help='Creates an archive for every supported image')
        parser.add_argument('-d', '--download', action='store_true',
                            help='Download image from repository instead of building it')

    def handle(self, **options):
        image_name = options['name']
        memory = options['memory']
        num_cores = options['num_cores']
        headless = options['headless']
        clean = options['clean']
        archive = options['archive']
        download = options['download']

        # If DISPLAY is missing, don't use headless mode
        if headless:
            self._headless = True

        if not image_name:
            self._print_image_list()
            return

        self._check_ram_size(memory)
        self._check_core_num(num_cores)

        # The path could have been deleted by a previous clean
        if not os.path.exists(self.image_path()):
            os.makedirs(self.image_path())

        img_build_dir = self.source_path(CONSTANTS['repos']['images']['build'])
        templates = get_image_templates(img_build_dir)

        if image_name != 'all' and image_name not in templates:
            raise CommandError('Invalid image image_name %s' % image_name)

        if download:
            self._download_images(templates, image_name)
            return

        _check_groups()
        _check_vmlinux()

        rule_name = image_name

        if archive:
            rule_name = 'archive'
            if image_name != 'all':
                rule_name = os.path.join(self.image_path(), '%s.tar.xz' % image_name)

        env = os.environ.copy()

        env['S2E_INSTALL_ROOT'] = self.install_path()
        env['S2E_LINUX_KERNELS_ROOT'] = self.source_path(CONSTANTS['repos']['images']['linux'])
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

    def _print_image_list(self):
        img_build_dir = self.source_path(CONSTANTS['repos']['images']['build'])
        templates = get_image_templates(img_build_dir)

        if not templates:
            raise CommandError(
                'No images available to build. Make sure that %s/images.json exists and is valid' %
                img_build_dir
            )

        print('Available images:')

        for template, desc in templates.iteritems():
            print(' * %s - %s' % (template, desc['name']))

        print(' * all - Build all images')

        print('\nRun ``s2e image_build <name>`` to build an image. '
              'Note that you must run ``s2e build`` **before** building '
              'an image')

    def _check_ram_size(self, value):
        """
        Ensure that the amount of RAM is sensible.
        """
        if value <= 0 or value > 2 * 1024:
            self.warn('The specified memory size for the image looks too high. '
                      'Less than 2GB is recommended for best performance.')

    def _check_core_num(self, value):
        """
        Ensure that the number of CPU cores is sensible.
        """
        if value <= 0 or value > 10:
            self.warn('The specified number of cores seems high. '
                      'Less than 10 is recommended for best image building performance.')

    def _download_images(self, templates, image_name):
        images = []
        if image_name == 'all':
            images = templates.keys()
        else:
            images.append(image_name)

        for image in images:
            dest_file = self.image_path('%s.tar.xz' % image)
            self._download(templates[image]['url'], dest_file)
            self._decompress(dest_file)

    def _download(self, url, path):
        self.info('Downloading %s' % url)
        s2e_env.utils.google.download(url, path)

    def _decompress(self, path):
        self.info('Decompressing %s' % path)
        try:
            cwd = os.path.dirname(path)
            subprocess.check_call(['tar', 'xJvf', path], cwd=cwd)
        except subprocess.CalledProcessError:
            raise CommandError('Image decompression failed')

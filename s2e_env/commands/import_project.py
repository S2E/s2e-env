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


import json
import logging
import os
import shutil
import sys

# pylint: disable=no-name-in-module
from sh import tar, ErrorReturnCode

from s2e_env import CONSTANTS
from s2e_env.command import EnvCommand, CommandError
from s2e_env.commands.import_export import S2E_ENV_PLACEHOLDER, rewrite_files


logger = logging.getLogger('import')


def _get_project_name(archive):
    """
    Get the project name from the archive.

    The project name is the name of the root directory in the archive.
    """
    try:
        contents = tar(exclude='*/*', list=True, file=archive)
        return os.path.dirname(str(contents))
    except ErrorReturnCode as e:
        raise CommandError('Failed to list archive - %s' % e)


class Command(EnvCommand):
    """
    Import a project exported from another S2E environment.

    This command can be used on any archive exported via the ``s2e
    export_project`` command.

    All of the files in the archive will be exported to the new project, and
    those listed under ``exported_files`` in ``config.yaml`` will be rewritten
    so that the placeholder marker inserted by the ``s2e export_project``
    command is replaced by the S2E environment path.
    """

    help = 'Import an S2E project from an archive'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('archive', nargs=1,
                            help='The path to the exported project archive')
        parser.add_argument('-f', '--force', action='store_true',
                            help='If a project with the same name as the '
                                 'imported project already exists, replace it')

    def handle(self, *args, **options):
        # Check the archive
        archive = options['archive'][0]
        if not os.path.isfile(archive):
            raise CommandError('%s is not a valid project archive' % archive)

        # Get the name of the project that we are importing
        project_name = _get_project_name(archive)
        logger.info('Importing project \'%s\' from %s', project_name, archive)

        # Check if a project with that name already exists
        project_path = self.projects_path(project_name)
        if os.path.isdir(project_path):
            if options['force']:
                logger.info('\'%s\' already exists - removing', project_name)
                shutil.rmtree(self.projects_path(project_name))
            else:
                raise CommandError('\'%s\' already exists. Either remove this '
                                   'project or use the force option' % project_name)

        # Decompress the archive
        self._decompress_archive(archive)

        # Rewrite all of the exported files to fix their S2E environment paths
        logger.info('Rewriting project files')
        rewrite_files(project_path, CONSTANTS['import_export']['project_files'],
                      S2E_ENV_PLACEHOLDER, self.env_path())

        with open(os.path.join(project_path, 'project.json'), 'r') as f:
            proj_desc = json.load(f)

            if 'image' not in proj_desc:
                logger.error('No image description found in project.json. Unable '
                             'to determine the guest tools to symlink')
                return

            image_path = os.path.join(proj_desc['image'], 'image.json')
            if not os.path.exists(image_path):
                logger.error('%s does not exist, please check that the guest image is built properly', image_path)
                return

            with open(image_path, 'r') as fp:
                image = json.load(fp)

            # Create a symlink to the guest tools directory
            self._symlink_guest_tools(project_path, image)

            # Create a symlink to guestfs (if it exists)
            if proj_desc.get('has_guestfs'):
                self._symlink_guestfs(project_path, proj_desc['image'])

        logger.success('Project successfully imported from %s', archive)

    def _decompress_archive(self, archive_path):
        """
        Decompress the given archive into the S2E environment's projects
        directory.
        """
        try:
            logger.info('Decompressing archive %s', archive_path)
            tar(extract=True, xz=True, verbose=True, file=archive_path,
                directory=self.projects_path(), _fg=True, _out=sys.stdout,
                _err=sys.stderr)
        except ErrorReturnCode as e:
            raise CommandError('Failed to decompress project archive - %s' % e)

    def _symlink_guest_tools(self, project_path, image):
        """
        Create a symlink to the guest tools directory.
        """
        qemu_arch = image['qemu_build']
        guest_tools_path = \
            self.install_path('bin', CONSTANTS['guest_tools'][qemu_arch])

        logger.info('Creating a symlink to %s', guest_tools_path)
        os.symlink(guest_tools_path, os.path.join(project_path, 'guest-tools'))

    def _symlink_guestfs(self, project_path, image_name):
        """
        Create a symlink to the image's guestfs directory.
        """
        guestfs_path = self.image_path(image_name, 'guestfs')
        if not os.path.exists(guestfs_path):
            logger.warning('%s does not exist, despite the original project '
                           'using the guestfs. The VMI plugin may not run '
                           'optimally', guestfs_path)
            return

        logger.info('Creating a symlink to %s', guestfs_path)
        os.symlink(guestfs_path, os.path.join(project_path, 'guestfs'))

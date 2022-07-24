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
import tempfile

from s2e_env import CONSTANTS
from s2e_env.command import EnvCommand, CommandError
from s2e_env.commands.import_export import S2E_ENV_PLACEHOLDER, rewrite_files
from s2e_env.commands.project_creation import abstract_project
from s2e_env.utils.images import get_image_descriptor


logger = logging.getLogger('import')


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
        super().add_arguments(parser)

        parser.add_argument('archive', nargs=1,
                            help='The path to the exported project archive')
        parser.add_argument('-f', '--force', action='store_true',
                            help='If a project with the same name as the '
                                 'imported project already exists, replace it')
        parser.add_argument('-i', '--image', required=False,
                            help='Override the guest image')
        parser.add_argument('-n', '--project-name', required=False,
                            help='Override the project name')

    def handle(self, *args, **options):
        # Check the archive
        archive = options['archive'][0]
        if not os.path.isfile(archive):
            raise CommandError(f'{archive} is not a valid project archive')

        # Get the name of the project that we are importing
        project_name = options.get('project_name')

        logger.info('Importing project from %s', archive)

        project_path = self._decompress_archive(archive, project_name, options.get('force'))

        # Rewrite all of the exported files to fix their S2E environment paths
        logger.info('Rewriting project files')
        rewrite_files(project_path, CONSTANTS['import_export']['project_files'],
                      S2E_ENV_PLACEHOLDER, self.env_path())

        with open(os.path.join(project_path, 'project.json'), 'r', encoding='utf-8') as f:
            proj_desc = json.load(f)

            if 'image' not in proj_desc:
                logger.error('No image description found in project.json. Unable '
                             'to determine the guest tools to symlink')
                return

            override_image = options.get('image', None)
            if override_image:
                dn = os.path.dirname(proj_desc['image'])
                old_image = os.path.basename(proj_desc['image'])
                proj_desc['image'] = os.path.join(dn, override_image)

                rewrite_files(project_path, CONSTANTS['import_export']['project_files'],
                              old_image, override_image)

            image = get_image_descriptor(proj_desc['image'])

            # Create a symlink to the guest tools directory
            self._symlink_guest_tools(project_path, image)

            # Create a symlink to guestfs (if it exists)
            if proj_desc.get('has_guestfs'):
                self._symlink_guestfs(project_path, image)

        logger.success('Project successfully imported from %s to %s', archive, project_path)

    def _symlink_guest_tools(self, project_path, image):
        """
        Create a symlink to the guest tools directory.
        """
        abstract_project.symlink_guest_tools(self.install_path(), project_path, image)

    def _symlink_guestfs(self, project_path, image):
        """
        Create a symlink to the image's guestfs directory.
        """
        guestfs_paths = abstract_project.select_guestfs(self.image_path(), image)
        abstract_project.symlink_guestfs(project_path, guestfs_paths)

    def _decompress_archive(self, archive_path, project_name, overwrite):
        """
        Decompress the given archive into the S2E environment's projects directory.
        """
        try:
            with tempfile.TemporaryDirectory() as directory:
                logger.info('Decompressing archive %s to %s', archive_path, directory)
                shutil.unpack_archive(archive_path, directory)

                files = os.listdir(directory)
                if len(files) != 1:
                    raise Exception(f'Archive {archive_path} is invalid')

                src_proj_name = files[0]
                src_proj_path = os.path.join(directory, src_proj_name)
                if not os.path.isdir(src_proj_path):
                    raise Exception(f'{src_proj_path} is not a directory')

                # Check if a project with that name already exists
                if not project_name:
                    project_name = src_proj_name

                project_path = self.projects_path(project_name)
                if os.path.isdir(project_path):
                    if overwrite:
                        logger.info('\'%s\' already exists - removing', project_path)
                        shutil.rmtree(project_path)
                    else:
                        raise CommandError(f'\'{project_name}\' already exists. Either remove this '
                                        'project or use the force option')

                shutil.move(src_proj_path, project_path)

                return project_path

        except Exception as e:
            raise CommandError(f'Failed to decompress project archive - {e}') from e

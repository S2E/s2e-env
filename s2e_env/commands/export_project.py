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
# No name 'tar' in module 'sh'
from sh import tar, ErrorReturnCode

try:
    from tempfile import TemporaryDirectory
except ImportError:
    from s2e_env.utils.tempdir import TemporaryDirectory

from s2e_env import CONSTANTS
from s2e_env.command import ProjectCommand, CommandError
from s2e_env.commands.import_export import S2E_ENV_PLACEHOLDER, rewrite_files


logger = logging.getLogger('export')


class Command(ProjectCommand):
    """
    Export a project so that it can be shared with other S2E environments.

    All files listed under ``exported_files`` in ``config.yaml`` will be
    exported. Each of these files will be checked for references to the S2E
    environment path, and all occurances of this path will be replaced by a
    placeholder marker. When importing the project into a new S2E environment,
    this placeholder will be rewritten with the path of the new S2E
    environment.

    The user can also export previous analysis results (i.e. all of the
    ``s2e-out-*`` directories) if required.
    """

    help = 'Export an S2E project as an archive'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('output_path', nargs='?',
                            help='The path to the exported project archive. '
                                 'Defaults to <project_name>.tar.xz in the '
                                 'current working directory')
        parser.add_argument('-r', '--export-results', action='store_true',
                            help='Export the results in the s2e-out-* directories')

    def handle(self, *args, **options):
        # Name the project archive if it doesn't already have a name
        output_path = options['output_path']
        if not output_path:
            output_path = self.env_path('%s.tar.xz' % self.project_name)

        with TemporaryDirectory() as temp_dir:
            # Store all of the exported files in a temporary directory so that
            # we can just execute tar on the entire directory
            export_dir = os.path.join(temp_dir, self.project_name)

            # Do **not** export these files
            blacklist = CONSTANTS['import_export']['blacklist']
            if not options['export_results']:
                blacklist.extend(['s2e-last', 's2e-out-*'])

            # Copy the project directory
            logger.info('Copying project %s', self.project_name)
            shutil.copytree(self.project_path(), export_dir,
                            ignore=shutil.ignore_patterns(*blacklist))

            # Rewrite certain project files (e.g., launch-s2e.sh, etc.) to
            # remove the absolute path to the current S2E environment. This
            # path is replaced with a placeholder token which is then rewritten
            # with the absolute path of the new S2E environment when the
            # project is imported
            logger.info('Rewriting project files')
            rewrite_files(export_dir,
                          CONSTANTS['import_export']['project_files'],
                          self.env_path(), S2E_ENV_PLACEHOLDER)

            # Update project.json
            #
            # project.json has already had its S2E environment path
            # overwritten. However, there are still other paths that need
            # rewriting to ensure that the project can be correctly imported.
            logger.info('Updating project.json')
            with open(os.path.join(export_dir, 'project.json'), 'r+') as f:
                proj_desc = json.load(f)

                # The target files in a project are normally symbolic links.
                # However, when exported they are no longer symbolic links and
                # so we must update their paths

                proj_path = proj_desc['project_dir']
                update_path = lambda p: os.path.join(proj_path, os.path.basename(p))

                target_path = proj_desc.get('target_path')
                if target_path:
                    proj_desc['target_path'] = update_path(target_path)

                target_files = proj_desc.get('target_files')
                if target_files:
                    proj_desc['target_files'] = [update_path(tf) for tf in target_files]

                # Update the project.json in the temporary directory
                proj_desc_json = json.dumps(proj_desc, sort_keys=True, indent=4)
                f.seek(0)
                f.write(proj_desc_json)
                f.truncate()

            # Create the archive of the temporary directory's contents
            self._create_archive(output_path, temp_dir)

        logger.success('Project successfully exported to %s', output_path)

    def _create_archive(self, archive_path, export_dir):
        """
        Create the final archive of all the exported project files.

        Args:
            archive_path: Path to the ``tar.xz`` archive.
            export_dir: Path to the directory containing the files to export.
        """
        try:
            logger.info('Creating archive %s', archive_path)
            create_archive = tar.bake(create=True, xz=True, verbose=True,
                                      file=archive_path, directory=export_dir,
                                      _out=sys.stdout,
                                      _err=sys.stderr)
            create_archive(self._project_name)
        except ErrorReturnCode as e:
            raise CommandError('Failed to archive project - %s' % e)

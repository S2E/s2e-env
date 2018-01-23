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


import glob
import json
import logging
import os
import shutil
import sys

from sh import tar, ErrorReturnCode

try:
    from tempfile import TemporaryDirectory
except ImportError:
    from s2e_env.utils.tempdir import TemporaryDirectory

from s2e_env.command import ProjectCommand, CommandError
from s2e_env.commands.import_export import S2E_ENV_PLACEHOLDER, copy_and_rewrite_files


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
            output_path = self.env_path('%s.tar.xz' % self._project_name)

        with TemporaryDirectory() as temp_dir:
            # Store all of the exported files in a temporary directory so that
            # we can just execute tar on the entire directory
            export_dir = os.path.join(temp_dir, self._project_name)
            os.mkdir(export_dir)

            # Copy project scripts and config files and rewrite the S2E
            # environment path in these files
            logger.info('Rewriting project files')
            copy_and_rewrite_files(self.project_path(), export_dir,
                                   self.env_path(), S2E_ENV_PLACEHOLDER)

            with open(self.project_path('project.json'), 'r') as orig_proj_file, \
                 open(os.path.join(export_dir, 'project.json'), 'r+') as new_proj_file:
                orig_proj_desc = json.load(orig_proj_file)
                new_proj_desc = json.load(new_proj_file)

                # Rewrite the target_path entry in the given project.json. This
                # is done because when we import the project the target will no
                # longer be a symlink
                new_proj_desc['target_path'] = \
                    os.path.join(new_proj_desc['project_dir'], new_proj_desc['target'])

                # Export the recipes directory. We need a reference to the
                # original project description so that we know where to copy
                # from (because our new project description has been
                # overwritten with the S2E_ENV_PLACEHOLDER)
                if new_proj_desc['use_recipes']:
                    recipes_dir = os.path.basename(new_proj_desc['recipes_dir'])
                    shutil.copytree(orig_proj_desc['recipes_dir'],
                                    os.path.join(export_dir, recipes_dir))

                # Export the seeds directory. We need a reference to the
                # original project description so that we know where to copy
                # from (because the new project description has been
                # overwritten with the S2E_ENV_PLACEHOLDER)
                if new_proj_desc['use_seeds']:
                    seeds_dir = os.path.basename(new_proj_desc['seeds_dir'])
                    shutil.copytree(orig_proj_desc['seeds_dir'],
                                    os.path.join(export_dir, seeds_dir))

                # Update the project.json in the temporary directory
                new_proj_desc_json = json.dumps(new_proj_desc, sort_keys=True, indent=4)
                new_proj_file.seek(0)
                new_proj_file.write(new_proj_desc_json)
                new_proj_file.truncate()

            # Copy the target into the temporary directory
            logger.info('Copying target from %s', self._project_desc['target_path'])
            shutil.copyfile(self._project_desc['target_path'],
                            os.path.join(export_dir, self._project_desc['target']))

            # Copy previous results
            if options['export_results']:
                self._copy_previous_results(export_dir)

            # Create the archive of the temporary directory's contents
            self._create_archive(output_path, temp_dir)

        logger.success('Project successfully exported to %s', output_path)

    def _copy_previous_results(self, export_dir):
        """
        Copy previous S2E analysis results for this project.

        Args:
            export_dir: Path to the temporary directory that will be exported.
        """
        for s2e_out_path in glob.glob(self.project_path('s2e-out-*')):
            s2e_out_dir = os.path.basename(s2e_out_path)
            logger.info('Copying %s', s2e_out_dir)
            shutil.copytree(s2e_out_path, os.path.join(export_dir, s2e_out_dir))

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
                                      _fg=True, _out=sys.stdout,
                                      _err=sys.stderr)
            create_archive(self._project_name)
        except ErrorReturnCode as e:
            raise CommandError('Failed to archive project - %s' % e)

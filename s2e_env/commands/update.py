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


import logging
import os
import sys

import sh
from sh import ErrorReturnCode

from s2e_env.command import EnvCommand, CommandError


logger = logging.getLogger('update')


class Command(EnvCommand):
    """
    Updates the S2E repos.
    """

    help = 'Updates the S2E repos.'

    def handle(self, *args, **options):
        self._update_s2e_sources()
        logger.success('Environment updated. Now run ``s2e build`` to rebuild')

    def _update_s2e_sources(self):
        """
        Update all of the S2E repositories with repo.
        """
        repo = sh.Command(self.install_path('bin', 'repo'))

        # cd into the S2E source directory
        orig_dir = os.getcwd()

        repo_dir = self.source_path('.repo')
        if not os.path.exists(repo_dir):
            raise CommandError(
                '%s does not exist. Your environment is not supported by this version of s2e-env.\n'
                'Please create a new environment.' % (repo_dir)
            )

        os.chdir(self.source_path())

        try:
            logger.info('Updating S2E')
            repo.sync(_out=sys.stdout, _err=sys.stderr)
        except ErrorReturnCode as e:
            raise CommandError(e)
        finally:
            # Change back to the original directory
            os.chdir(orig_dir)

        # Success!
        logger.info('Updated S2E')

import os
import sys

import sh
from sh import git, ErrorReturnCode

from s2e_env import CONSTANTS
from s2e_env.command import EnvCommand, CommandError


class Command(EnvCommand):
    """
    Updates the S2E repos.
    """

    help = 'Updates the S2E repos.'

    def handle(self):
        self._update_s2e_sources()
        self._update_img_sources()

        return 'Environment updated. Now run ``s2e build`` to rebuild'

    def _update_s2e_sources(self):
        """
        Update all of the S2E repositories with repo.
        """
        s2e_source_path = self.env_path('source', 's2e')
        repo = sh.Command(self.env_path('bin', 'repo'))

        # cd into the S2E source directory
        orig_dir = os.getcwd()
        os.chdir(s2e_source_path)

        try:
            self.info('Updating s2e')
            repo.sync(_out=sys.stdout, _err=sys.stderr, _fg=True)
        except ErrorReturnCode as e:
            raise CommandError(e)
        finally:
            # Change back to the original directory
            os.chdir(orig_dir)

        # Success!
        self.success('Updated s2e')

    def _update_img_sources(self):
        """
        Update the S2E image repositories.
        """
        git_repos = CONSTANTS['repos']['images'].values()

        for git_repo in git_repos:
            git_repo_dir = self.env_path('source', git_repo)

            if not os.path.isdir(git_repo_dir):
                self.warn('%s does not exist. Skipping' % git_repo)
                continue

            try:
                self.info('Updating %s' % git_repo)
                git.bake(C=git_repo_dir).pull(_out=sys.stdout, _err=sys.stderr,
                                              _fg=True)
            except ErrorReturnCode as e:
                raise CommandError(e)

            # Success!
            self.success('Updated %s' % git_repo)

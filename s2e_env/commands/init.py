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


import os
import shutil
import stat
import sys

import requests
import sh
from sh import ErrorReturnCode
from sh.contrib import sudo

from s2e_env import CONSTANTS
from s2e_env.command import BaseCommand, CommandError
from s2e_env.utils import repos


def _get_img_sources(env_path):
    """
    Download the S2E image repositories.
    """
    git_repos = CONSTANTS['repos']['images'].values()

    for git_repo in git_repos:
        repos.git_clone_to_source(env_path, git_repo)


class Command(BaseCommand):
    """
    Initializes a new S2E environment.

    This involves cloning the S2E repos into the current directory.
    """

    help = 'Initializes a new S2E environment.'

    def add_arguments(self, parser):
        parser.add_argument('dir', help='The environment directory')
        parser.add_argument('-s', '--skip-dependencies', action='store_true',
                            help='Skip the dependency install via apt')
        parser.add_argument('-b', '--use-existing-install', required=False,
                            default=None,
                            help='Do not fetch sources but instead use an '
                                 'existing S2E installation whose prefix is '
                                 'specified by this parameter (e.g., /opt/s2e)')
        parser.add_argument('-f', '--force', action='store_true',
                            help='Use this flag to force environment creation '
                                 'even if an environment already exists at '
                                 'this location')

    def handle(self, *args, **options):
        env_path = os.path.realpath(options['dir'])
        force = options['force']
        prefix = options['use_existing_install']

        # First check if we are already in the environment directory
        if os.path.realpath(env_path) == os.path.realpath(os.getcwd()):
            raise CommandError('You cannot create an S2E environment in the '
                               'current working directory. Please `cd ..`')

        # Then check if something already exists at the environment directory
        if os.path.isdir(env_path) and not os.listdir(env_path) == []:
            if force:
                self.info('%s already exists - removing' % env_path)
                shutil.rmtree(env_path)
            else:
                raise CommandError('Something already exists at \'%s\'. '
                                   'Please select a different location or use '
                                   'the ``force`` option to erase this '
                                   'environment.\n\nDid you mean to rebuild or '
                                   'update your existing environment? Try '
                                   '``s2e build`` or ``s2e update`` instead' %
                                   env_path)


        # Create environment if it doesn't exist
        self.info('Creating environment in %s' % env_path)
        if not os.path.isdir(env_path):
            os.mkdir(env_path)

        # Create the directories within the environment
        for dir_ in CONSTANTS['dirs']:
            os.mkdir(os.path.join(env_path, dir_))

        # Create marker file to recognize s2e environment folder
        with open(os.path.join(env_path, '.s2eenv'), 'w'):
            pass

        if prefix is not None:
            self._install_binary_dist(env_path, prefix)
            return 'Environment created in %s.' % env_path
        else:
            # Install S2E's dependencies via apt-get
            if not options['skip_dependencies']:
                self._install_dependencies()

            # Get the source repositories
            self._get_s2e_sources(env_path)
            _get_img_sources(env_path)

            return ('Environment created in %s. Now run ``s2e build`` to build'
                    % env_path)

    def _install_binary_dist(self, env_path, prefix):
        # We must use an absolute path because of symlinks
        prefix = os.path.abspath(prefix)

        self.info('Using S2E installation in %s' % prefix)
        install = os.path.join(env_path, 'install')
        shutil.rmtree(install, True)
        os.symlink(prefix, install)

        # We still need to clone guest-images repo, because it contains
        # info about location of the images
        guest_images_repo = CONSTANTS['repos']['images']['build']
        repos.git_clone_to_source(env_path, guest_images_repo)

    def _install_dependencies(self):
        """
        Install S2E's dependencies.

        Only apt-get is supported for now.
        """
        self.info('Installing S2E dependencies')

        ubuntu_ver = self._get_ubuntu_version()
        if not ubuntu_ver:
            return

        install_packages = CONSTANTS['dependencies']['common'] + \
                           CONSTANTS['dependencies']['ubuntu_%d' % ubuntu_ver]

        # Check for IDA Pro. If it has been specified, we will install its
        # packages too
        if CONSTANTS['ida']['dir']:
            install_packages += CONSTANTS['dependencies']['ida']

        try:
            apt_get = sudo.bake('apt-get', _fg=True)

            # Perform apt-get install
            apt_get.install(install_packages)
        except ErrorReturnCode as e:
            raise CommandError(e)

    def _get_ubuntu_version(self):
        """
        Gets the "major" Ubuntu version.

        If an unsupported OS/Ubuntu version is found a warning is printed and
        ``None`` is returned.
        """
        import platform

        distname, version, _ = platform.dist()

        if distname.lower() != 'ubuntu':
            self.warn('You are running on a non-Ubuntu system. Skipping S2E '
                      'dependencies - please install them manually')
            return None

        major_version = int(version.split('.')[0])

        if major_version < 14:
            self.warn('You are running an unsupported version of Ubuntu. '
                      'Skipping S2E dependencies  - please install them '
                      'manually')
            return None

        return major_version

    def _get_s2e_sources(self, env_path):
        """
        Download the S2E manifest repository and initialize all of the S2E
        repositories with repo.
        """
        # Download repo
        repo = self._get_repo(env_path)

        s2e_source_path = os.path.join(env_path, 'source', 's2e')

        # Create the S2E source directory and cd to it to run repo
        os.mkdir(s2e_source_path)
        orig_dir = os.getcwd()
        os.chdir(s2e_source_path)

        git_url = CONSTANTS['repos']['url']
        git_s2e_repo = CONSTANTS['repos']['s2e']

        try:
            # Now use repo to initialize all the repositories
            self.info('Fetching %s from %s' % (git_s2e_repo, git_url))
            repo.init(u='%s/%s' % (git_url, git_s2e_repo), _out=sys.stdout,
                      _err=sys.stderr, _fg=True)
            repo.sync(_out=sys.stdout, _err=sys.stderr, _fg=True)
        except ErrorReturnCode as e:
            # Clean up - remove the half-created S2E environment
            shutil.rmtree(env_path)
            raise CommandError(e)
        finally:
            # Change back to the original directory
            os.chdir(orig_dir)

        # Success!
        self.success('Fetched %s' % git_s2e_repo)

    def _get_repo(self, env_path):
        """
        Create the repo command.

        If the repo binary does not exist, download it.
        """
        repo_path = os.path.join(env_path, 'install', 'bin', 'repo')
        if not os.path.isfile(repo_path):
            self._download_repo(repo_path)

        return sh.Command(repo_path)

    def _download_repo(self, repo_path):
        """
        Download repo.
        """
        self.info('Fetching repo')

        repo_url = CONSTANTS['repo']['url']
        response = requests.get(repo_url)

        if response.status_code != 200:
            raise CommandError('Unable to download repo from %s' % repo_url)

        with open(repo_path, 'wb') as f:
            f.write(response.content)

        self.success('Fetched repo')

        # Ensure that the repo binary is executable
        st = os.stat(repo_path)
        os.chmod(repo_path, st.st_mode | stat.S_IEXEC)

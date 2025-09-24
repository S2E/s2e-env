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

import datetime
import logging
import os
import shutil
import stat
import sys
import urllib

import distro
import requests
import sh
from sh import ErrorReturnCode

# pylint: disable=import-error
from sh.contrib import sudo

from s2e_env import CONSTANTS
from s2e_env.command import BaseCommand, CommandError
from s2e_env.utils import repos
from s2e_env.utils.templates import render_template

logger = logging.getLogger('init')


def _link_existing_install(env_path, existing_install):
    """
    Reuse an existing S2E installation at ```existing_install``` in the new
    environment at ```env_path```.
    """
    # Check that the expected S2E installation directories exist
    for dir_ in ('bin', os.path.join('share', 'libs2e')):
        if not os.path.isdir(os.path.join(existing_install, dir_)):
            raise CommandError(f'Invalid S2E installation - ``{dir_}`` does not '
                               'exist. Are you sure that this directory '
                               'contains a valid S2E installation?')

    logger.info('Using existing S2E installation at %s', existing_install)

    # Clear out anything that may exist in the new environment's install dir
    new_install = os.path.join(env_path, 'install')
    shutil.rmtree(new_install, True)

    # We must use an absolute path for symlinks
    os.symlink(os.path.abspath(existing_install), new_install)

    # We still need to clone guest-images repo, because it contains info about
    # the location of images
    guest_images_repo = CONSTANTS['repos']['images']['build']
    repos.git_clone_to_source(env_path, guest_images_repo)


def _compute_dependencies():
    version = _get_os_version()
    if not version:
        return []

    os_name, major_version = version

    logger.info('Detected OS:%s version:%s', os_name, major_version)

    deps = CONSTANTS['dependencies']

    all_install_packages = []

    common = deps.get('common', [])
    common_os = deps.get(f'common-{os_name}', [])
    os_specific = deps.get(f'{os_name}-{major_version}')

    if common:
        all_install_packages += common
        logger.debug('Common packages: %s', common)
    if common_os:
        all_install_packages += common_os
        logger.debug('OS-common packages: %s', common_os)
    if os_specific:
        all_install_packages += os_specific
        logger.debug('OS-specific packages: %s', os_specific)

    return all_install_packages


def install_dependencies():
    """
    Install S2E's dependencies.

    Only apt-get is supported for now.
    """
    logger.info('Installing S2E dependencies')

    all_install_packages = _compute_dependencies()
    if not all_install_packages:
        return

    install_packages = []
    deb_package_urls = []
    for package in all_install_packages:
        if '.deb' in package:
            deb_package_urls.append(package)
        else:
            install_packages.append(package)

    install_opts = ['--no-install-recommends']
    env = {}

    env['DEBIAN_FRONTEND'] = 'noninteractive'
    install_opts = ['-y'] + install_opts

    try:
        # Enable 32-bit libraries
        dpkg_add_arch = sudo.bake('dpkg', add_architecture=True, _fg=True)
        dpkg_add_arch('i386')

        # Perform apt-get install
        apt_get = sudo.bake('apt-get', _fg=True, _env=env)
        apt_get.update()
        apt_get.install(install_opts + install_packages)
    except ErrorReturnCode as e:
        raise CommandError(e) from e

    # Install deb files at the end
    for url in deb_package_urls:
        logger.info('Installing deb %s...', url)
        filename, _ = urllib.request.urlretrieve(url)
        os.rename(filename, f'{filename}.deb')
        apt_get = sudo.bake('apt-get', _fg=True, _env=env)
        apt_get.install(install_opts + [f'{filename}.deb'])


def _get_os_version():
    supported_oses = ['ubuntu', 'debian']
    id_name, version, _ = distro.linux_distribution(full_distribution_name=False)
    id_name = id_name.lower()

    if id_name not in supported_oses:
        logger.warning('You are running an unsupported Linux distribution (%s %s). Skipping S2E '
                       'dependencies - please install them manually', id_name, version)
        logger.info('Supported OSes: %s', ", ".join(supported_oses))
        return None

    major_version = int(version.split('.')[0])

    if major_version not in CONSTANTS['required_versions'][f'{id_name}_major_ver']:
        logger.warning('You are running an unsupported version of %s (%s). '
                       'Skipping S2E dependencies - please install them '
                       'manually', id_name, version)
        return None

    return id_name, major_version


def _get_s2e_sources(env_path, manifest_branch):
    """
    Download the S2E manifest repository and initialize all of the S2E
    repositories with repo. All required repos are in the manifest,
    no need to manually clone other repos.
    """
    # Download repo
    repo = _get_repo(env_path)

    source_path = os.path.join(env_path, 'source')

    # Create the S2E source directory and cd to it to run repo
    orig_dir = os.getcwd()
    os.chdir(source_path)

    git_url = CONSTANTS['repos']['url']
    git_s2e_repo = CONSTANTS['repos']['s2e']

    try:
        # Now use repo to initialize all the repositories
        logger.info('Fetching %s from %s', git_s2e_repo, git_url)
        repo.init(u=f'{git_url}/{git_s2e_repo}', b=manifest_branch,
                  _out=sys.stdout, _err=sys.stderr)
        repo.sync(_out=sys.stdout, _err=sys.stderr)
    except ErrorReturnCode as e:
        # Clean up - remove the half-created S2E environment
        shutil.rmtree(env_path)
        raise CommandError(e) from e
    finally:
        # Change back to the original directory
        os.chdir(orig_dir)

    # Success!
    logger.success('Fetched %s', git_s2e_repo)


def _get_repo(env_path):
    """
    Create the repo command.

    If the repo binary does not exist, download it.
    """
    repo_path = os.path.join(env_path, 'install', 'bin', 'repo')
    if not os.path.isfile(repo_path):
        _download_repo(repo_path)

    return sh.Command(repo_path)


def _download_repo(repo_path):
    """
    Download Google's repo.
    """
    logger.info('Fetching repo')

    repo_url = CONSTANTS['repo']['url']
    response = requests.get(repo_url, timeout=3600)

    if response.status_code != 200:
        raise CommandError(f'Unable to download repo from {repo_url}')

    with open(repo_path, 'wb') as f:
        f.write(response.content)

    logger.success('Fetched repo')

    # Ensure that the repo binary is executable
    st = os.stat(repo_path)
    os.chmod(repo_path, st.st_mode | stat.S_IEXEC)


def _create_config(env_path):
    """
    Create the YAML config file for the new environment.
    """
    s2e_yaml = 's2e.yaml'
    version_path = os.path.join(os.path.dirname(__file__), '..', 'dat', 'VERSION')

    with open(version_path, 'r', encoding='utf-8') as fp:
        context = {
            'creation_time': str(datetime.datetime.now()),
            'version': fp.read().strip(),
        }

    render_template(context, s2e_yaml, os.path.join(env_path, s2e_yaml))


def _create_activate_script(env_path):
    """
    Create the environment activation script.
    """
    # TODO detect shell to determine template
    template = 's2e_activate.sh'

    context = {
        'creation_time': str(datetime.datetime.now()),
        'S2EDIR': env_path,
    }

    render_template(context, template, os.path.join(env_path, 's2e_activate'))


class Command(BaseCommand):
    """
    Initializes a new S2E environment.

    This involves cloning the S2E repos into the current directory.
    """

    help = 'Initializes a new S2E environment.'

    def add_arguments(self, parser):
        parser.add_argument('dir', nargs='?', default=os.getcwd(),
                            help='The environment directory. Defaults to the '
                                 'current working directory')
        parser.add_argument('--install-dependencies', action='store_true',
                            required=False, default=True,
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
        parser.add_argument('-mb', '--manifest-branch', type=str, required=False, default='master',
                            help='Specify an alternate branch for the repo manifest')

    def handle(self, *args, **options):
        env_path = os.path.realpath(options['dir'])

        # Check if something already exists at the environment directory
        if os.path.isdir(env_path) and not os.listdir(env_path) == []:
            if options['force']:
                logger.info('%s already exists - removing', env_path)
                shutil.rmtree(env_path)
            else:
                raise CommandError(f'Something already exists at \'{env_path}\'. '
                                   'Please select a different location or use '
                                   'the ``force`` option to erase this '
                                   'environment.\n\nDid you mean to rebuild or '
                                   'update your existing environment? Try '
                                   '``s2e build`` or ``s2e update`` instead')

        try:
            # Create environment if it doesn't exist
            logger.info('Creating environment in %s', env_path)
            if not os.path.isdir(env_path):
                os.mkdir(env_path)

            # Create the directories within the environment
            for dir_ in CONSTANTS['dirs']:
                os.mkdir(os.path.join(env_path, dir_))

            # Create the YAML config for the environment
            _create_config(env_path)

            # Create the shell script to activate the environment
            _create_activate_script(env_path)

            s2e_activate_path = os.path.join(env_path, 's2e_activate')
            msg = f'Environment created in {env_path}. You may wish to modify your ' \
                  f'environment\'s s2e.yaml config file. Source ``{s2e_activate_path}`` to ' \
                  'activate your environment'

            existing_install_path = options['use_existing_install']
            if existing_install_path:
                _link_existing_install(env_path, existing_install_path)
            else:
                # Install S2E's dependencies via apt-get
                if options['install_dependencies']:
                    install_dependencies()

                # Get the source repositories
                _get_s2e_sources(env_path, options['manifest_branch'])

                # Remind the user that they must build S2E
                msg = f'{msg}. Then run ``s2e build`` to build S2E'

            logger.success(msg)
        except:
            # Cleanup on failure. Note that this only occurs if the chosen
            # directory is *not* the current working directory
            if os.path.isdir(env_path) and os.getcwd() != env_path:
                shutil.rmtree(env_path)
            raise

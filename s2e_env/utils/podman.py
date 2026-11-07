"""
Copyright (c) 2026 Vitaly Chipounov

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

# Checks that the host can run the rootless Podman containers that build the S2E
# tools and the guest kernels.

import json
import logging
import shutil
import subprocess

from s2e_env.command import CommandError


logger = logging.getLogger('podman')

# The Debian and Ubuntu base images contain files owned by UID and GID 65534
# (nobody). Pulling them fails unless the user namespace maps container IDs 0
# to 65534, i.e., at least 65535 IDs.
MIN_MAPPED_IDS = 65535

STORAGE_CONF_HINT = (
    'Add the following to ~/.config/containers/storage.conf (or to '
    '/etc/containers/storage.conf) to use the faster overlay driver, then run '
    '"podman system reset". That command deletes all existing Podman images '
    'and containers.\n\n'
    '\t[storage]\n'
    '\tdriver = "overlay"'
)


def _podman_info():
    """
    Run ``podman info`` and return its parsed JSON output.

    Raises a ``CommandError`` when podman is missing or ``podman info`` fails.
    """
    if not shutil.which('podman'):
        raise CommandError('podman is not installed. Install the podman and uidmap '
                           'packages, then log out and log in.')

    try:
        result = subprocess.run(['podman', 'info', '--format', 'json'],
                                capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise CommandError('"podman info" failed. If you have just installed podman, '
                           'log out and log in so that the user session bus is '
                           f'available.\n\n{e.stderr.strip()}') from e

    return json.loads(result.stdout)


def _mapped_ids(id_map):
    """
    Return the number of container IDs mapped by a ``podman info`` UID or GID map.
    """
    return sum(entry['size'] for entry in id_map or [])


def check_podman():
    """
    Check that rootless Podman is installed and usable.

    Raises a ``CommandError`` when Podman is missing, does not work, runs rootful,
    or when the user's subordinate UID or GID range is too small. Warns when
    Podman uses the slow ``vfs`` storage driver.
    """
    info = _podman_info()

    if not info['host']['security']['rootless']:
        raise CommandError('Podman must run rootless. Do not run s2e with sudo, '
                           'and do not point CONTAINER_HOST to a rootful Podman service.')

    id_mappings = info['host']['idMappings']
    for kind in ('uid', 'gid'):
        count = _mapped_ids(id_mappings[f'{kind}map'])
        if count < MIN_MAPPED_IDS:
            raise CommandError(f'Rootless Podman maps only {count} {kind.upper()}s, at least '
                               f'{MIN_MAPPED_IDS} are required. Add a subordinate {kind.upper()} '
                               f'range for your user to /etc/sub{kind}, for example with:\n\n'
                               '\tsudo usermod --add-subuids 100000-165535 '
                               '--add-subgids 100000-165535 $(whoami)\n\n'
                               'Then run "podman system migrate".')

    if info['store']['graphDriverName'] == 'vfs':
        logger.warning('Podman uses the vfs storage driver, which stores a full copy of every '
                       'image layer and makes builds slow. %s', STORAGE_CONF_HINT)

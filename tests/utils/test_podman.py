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


import copy
import json
import subprocess
from unittest import TestCase
from unittest.mock import patch

from s2e_env.command import CommandError
from s2e_env.utils import podman


# Default rootless setup: the calling user plus 65536 subordinate IDs
ID_MAP = [
    {'container_id': 0, 'host_id': 1000, 'size': 1},
    {'container_id': 1, 'host_id': 100000, 'size': 65536},
]

PODMAN_INFO = {
    'host': {
        'security': {'rootless': True},
        'idMappings': {'uidmap': ID_MAP, 'gidmap': ID_MAP},
    },
    'store': {'graphDriverName': 'overlay'},
}


def _completed(info):
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps(info), stderr='')


@patch('s2e_env.utils.podman.shutil.which', return_value='/usr/bin/podman')
@patch('s2e_env.utils.podman.subprocess.run')
class CheckPodmanTestCase(TestCase):
    def _info(self):
        return copy.deepcopy(PODMAN_INFO)

    def test_ok(self, run, _which):
        run.return_value = _completed(self._info())
        with self.assertNoLogs('podman'):
            podman.check_podman()

    def test_missing_binary(self, run, which):
        which.return_value = None
        with self.assertRaisesRegex(CommandError, 'podman is not installed'):
            podman.check_podman()
        run.assert_not_called()

    def test_info_fails(self, run, _which):
        run.side_effect = subprocess.CalledProcessError(
            125, ['podman', 'info'], stderr='sd-bus call: Permission denied')
        with self.assertRaisesRegex(CommandError, 'log out and log in'):
            podman.check_podman()

    def test_rootful(self, run, _which):
        info = self._info()
        info['host']['security']['rootless'] = False
        run.return_value = _completed(info)
        with self.assertRaisesRegex(CommandError, 'must run rootless'):
            podman.check_podman()

    def test_vfs_driver_warns(self, run, _which):
        info = self._info()
        info['store']['graphDriverName'] = 'vfs'
        run.return_value = _completed(info)
        with self.assertLogs('podman', level='WARNING') as logs:
            podman.check_podman()
        self.assertIn('driver = "overlay"', logs.output[0])

    def test_single_uid_entry(self, run, _which):
        # No subordinate UIDs: only the calling user is mapped
        info = self._info()
        info['host']['idMappings']['uidmap'] = ID_MAP[:1]
        run.return_value = _completed(info)
        with self.assertRaisesRegex(CommandError, 'maps only 1 UIDs'):
            podman.check_podman()

    def test_small_gid_range(self, run, _which):
        info = self._info()
        info['host']['idMappings']['gidmap'] = [
            {'container_id': 0, 'host_id': 1000, 'size': 1},
            {'container_id': 1, 'host_id': 100000, 'size': 65533},
        ]
        run.return_value = _completed(info)
        with self.assertRaisesRegex(CommandError, 'maps only 65534 GIDs'):
            podman.check_podman()

    def test_minimum_range(self, run, _which):
        # Container IDs 0 to 65534 are mapped, which covers nobody (65534)
        info = self._info()
        small = [
            {'container_id': 0, 'host_id': 1000, 'size': 1},
            {'container_id': 1, 'host_id': 100000, 'size': 65534},
        ]
        info['host']['idMappings'] = {'uidmap': small, 'gidmap': small}
        run.return_value = _completed(info)
        podman.check_podman()

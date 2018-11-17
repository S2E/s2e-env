"""
Copyright (c) 2018 Adrian Herrera

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
from tempfile import gettempdir
from unittest import TestCase

from mock import MagicMock

from s2e_env.commands.new_project import _extract_inf_files
from s2e_env.commands.project_creation.windows_project import WindowsProject, WindowsDriverProject
from . import DATA_DIR


WINDOWS_XPSP3_X86_IMAGE_DESC = {
    'path': os.path.join(gettempdir(), 'image.raw.s2e'),
    'name': 'Windows XP Professional SP3 i386',
    'image_group': 'windows',
    'url': '',
    'iso': {
        'name': 'en_windows_xp_professional_with_service_pack_3_x86_cd_x14-80428.iso',
        'sha1': '1c735b38931bf57fb14ebd9a9ba253ceb443d459'
    },
    'os': {
        'product_key': '',
        'name': 'windows',
        'version': 'xpsp3pro',
        'arch': 'i386',
        'build': '2600',
        'binary_formats': ['pe']
    },
    'hw': {
        'default_disk_size': '8G',
        'default_snapshot_size': '256M',
        'nic': 'pcnet'
    }
}

WINDOWS_7SP1_X64_IMAGE_DESC = {
    'path': os.path.join(gettempdir(), 'image.raw.s2e'),
    'name': 'Windows 7 Enterprise SP1 x86_64',
    'image_group': 'windows',
    'url': '',
    'iso': {
        'name': 'en_windows_7_enterprise_with_sp1_x64_dvd_u_677651.iso',
        'sha1': 'a491f985dccfb5863f31b728dddbedb2ff4df8d1'
    },
    'os': {
        'family': 'windows',
        'name': 'windows',
        'version': '7sp1ent',
        'arch': 'x86_64',
        'build': '7600.16385',
        'binary_formats': ['pe']
    },
    'hw': {
        'default_disk_size': '20G',
        'default_snapshot_size': '2G',
        'nic': 'e1000'
    }
}

SCANNER_INF = u'scanner.inf'
SCANNER_SYS = u'scanner.sys'
SCANNER_USER_EXE = u'scanuser.exe'

SCANNER_INF_PATH = os.path.join(DATA_DIR, SCANNER_INF)
SCANNER_SYS_PATH = os.path.join(DATA_DIR, SCANNER_SYS)
SCANNER_USER_EXE_PATH = os.path.join(DATA_DIR, SCANNER_USER_EXE)


class WindowsProjectTestCase(TestCase):
    def setUp(self):
        self._windows_project = WindowsProject()
        self._windows_project._select_image = MagicMock(return_value=WINDOWS_XPSP3_X86_IMAGE_DESC)
        self._windows_project._env_dir = MagicMock(return_value=gettempdir())

        self._windows_driver_project = WindowsDriverProject()
        self._windows_driver_project._select_image = MagicMock(return_value=WINDOWS_7SP1_X64_IMAGE_DESC)
        self._windows_driver_project._env_dir = MagicMock(return_value=gettempdir())

    def test_empty_xpsp3pro_project_config(self):
        """Test empty Windows XP SP3 project creation."""
        args = {
            'image': 'windows-xpsp3pro-i386',
            'name': 'test',
            'target_files': [],
            'target_arch': None,
        }

        config = self._windows_project._make_config(**args)

        # Assert that we have actually created a Windows project
        self.assertEqual(config['project_type'], 'windows')

        # Assert that the project has no target
        self.assertIsNone(config['target_path'])
        self.assertIsNone(config['target_arch'])
        self.assertFalse(config['target_files'])

        # Should be empty when no target is specified
        self.assertFalse(config['processes'])

        # An empty project with no target will have no arguments
        self.assertFalse(config['target_args'])
        self.assertFalse(config['sym_args'])
        self.assertFalse(config['use_symb_input_file'])

        # Disabled by default
        self.assertFalse(config['enable_pov_generation'])
        self.assertFalse(config['use_seeds'])
        self.assertFalse(config['use_recipes'])
        self.assertFalse(config['use_fault_injection'])

    def test_scanner_driver_7sp1ent_x64_project_config(self):
        file_paths = _extract_inf_files(SCANNER_INF_PATH)
        args = {
            'target_files': list(set([SCANNER_INF_PATH] + file_paths)),
            'target_arch': 'x86_64',
        }

        config = self._windows_driver_project._make_config(**args)

        # Assert that we've actually created a Windows project
        self.assertEqual(config['project_type'], 'windows')

        # Assert that the target is the one given
        self.assertEqual(config['target_path'], SCANNER_INF_PATH)
        self.assertEqual(config['target_arch'], 'x86_64')
        self.assertItemsEqual(config['target_files'],
                              [SCANNER_INF_PATH, SCANNER_SYS_PATH, SCANNER_USER_EXE_PATH])

        # Assert that the x86_64 Windows 7 image was selected
        self.assertDictEqual(config['image'], WINDOWS_7SP1_X64_IMAGE_DESC)

        # Enabled by default for drivers
        self.assertTrue(config['use_fault_injection'])

        # Disabled by default
        self.assertFalse(config['enable_pov_generation'])
        self.assertFalse(config['use_seeds'])
        self.assertFalse(config['use_recipes'])
        self.assertFalse(config['processes'])

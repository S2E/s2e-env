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

from s2e_env.commands.project_creation import CGCProject, Target
from s2e_env.commands.new_project import target_from_file

from . import DATA_DIR, monkey_patch_project


CGC_IMAGE_DESC = {
    'path': os.path.join(gettempdir(), 'image.raw.s2e'),
    'name': 'Debian i386 image with CGC kernel and user-space packages',
    'image_group': 'linux',
    'url': 'localhost',
    'iso': {
        'url': 'localhost'
    },
    'os': {
        'name': 'cgc_debian',
        'version': '9.2.1',
        'arch': 'i386',
        'build': '',
        'binary_formats': ['decree']
    },
    'hw': {
        'default_disk_size': '4G',
        'default_snapshot_size': '256M',
        'nic': 'e1000'
    }
}

CADET_00001 = 'CADET_00001'
CADET_00001_PATH = os.path.join(DATA_DIR, CADET_00001)


class CGCProjectTestCase(TestCase):
    def test_empty_project_config(self):
        """Test empty CGC project creation."""
        target = Target.empty()
        project = monkey_patch_project(CGCProject(), CGC_IMAGE_DESC)
        options = {
            'image': 'cgc_debian-9.2.1-i386',
            'name': 'test',
        }

        config = project._configure(target, **options)

        # Assert that we have actually created a CGC project
        self.assertEqual(config['project_type'], 'cgc')

        # Assert that the projet has no target
        self.assertIsNone(config['target'].path)
        self.assertIsNone(config['target'].arch)
        self.assertFalse(config['target'].files)

        # Should be empty when no target is specified
        self.assertFalse(config['processes'])
        self.assertFalse(config['modules'])

        # CGC binaries have no input files
        self.assertFalse(target.args.raw_args)
        self.assertFalse(config['sym_args'])
        self.assertFalse(config['target'].args.symbolic_files)
        self.assertFalse(config['warn_input_file'])
        self.assertFalse(config['warn_seeds'])

        # CGC projects should always have POV generation, seeds and recipes
        # enabled
        self.assertTrue(config['enable_pov_generation'])
        self.assertTrue(config['use_seeds'])
        self.assertTrue(config['use_recipes'])

        # CGC has its own test case generation system
        self.assertFalse(config['use_test_case_generator'])

    def test_cadet0001_project_config(self):
        """
        Test CGC project creation given a CGC binary and nothing else. No
        image, project name, etc. is provided.
        """
        target, cls = target_from_file(CADET_00001_PATH)
        project = monkey_patch_project(cls(), CGC_IMAGE_DESC)

        config = project._configure(target)

        # Assert that we have actually created a CGC project
        self.assertEqual(config['project_type'], 'cgc')

        # Assert that the target is the one given (CADET_00001)
        self.assertEqual(config['target'].path, CADET_00001_PATH)
        self.assertEqual(config['target'].arch, 'i386')
        self.assertListEqual(config['target'].files, [CADET_00001_PATH])
        self.assertListEqual(config['processes'], [CADET_00001])
        self.assertListEqual(config['modules'], [(CADET_00001, False)])

        # Assert that the CGC image has been selected
        self.assertDictEqual(config['image'], CGC_IMAGE_DESC)

        # CGC binaries have no input files
        self.assertFalse(config['target'].args.raw_args)
        self.assertFalse(config['target'].args.symbolic_files)
        self.assertFalse(config['sym_args'])
        self.assertFalse(config['warn_input_file'])
        self.assertFalse(config['warn_seeds'])

        # CGC projects should always have POV generation, seeds and recipes
        # enabled
        self.assertTrue(config['enable_pov_generation'])
        self.assertTrue(config['use_seeds'])
        self.assertTrue(config['use_recipes'])

        # CGC has its own test case generation system
        self.assertFalse(config['use_test_case_generator'])

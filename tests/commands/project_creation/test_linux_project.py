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

from s2e_env.commands.project_creation import LinuxProject, Target
from s2e_env.commands.new_project import target_from_file

from . import DATA_DIR, monkey_patch_project


LINUX_IMAGE_DESC = {
    'path': os.path.join(gettempdir(), 'image.raw.s2e'),
    'name': 'Debian i386 image',
    'image_group': 'linux',
    'url': 'localhost',
    'iso': {
        'url': 'localhost'
    },
    'os': {
        'name': 'debian',
        'version': '9.2.1',
        'arch': 'i386',
        'build': '',
        'binary_formats': ['elf']
    },
    'hw': {
        'default_disk_size': '4G',
        'default_snapshot_size': '256M',
        'nic': 'e1000'
    }
}

CAT_X86 = 'cat'
CAT_X86_PATH = os.path.join(DATA_DIR, CAT_X86)


class LinuxProjectTestCase(TestCase):
    def test_empty_x86_project_config(self):
        """Test empty Linux x86 project creation."""
        target = Target.empty()
        project = monkey_patch_project(LinuxProject(), LINUX_IMAGE_DESC)

        options = {
            'image': 'debian-9.2.1-i386',
            'name': 'test',
        }

        config = project._configure(target, **options)

        # Assert that we have actually created a Linux project
        self.assertEqual(config['project_type'], 'linux')

        # Assert that the project has no target
        self.assertIsNone(config['target'].path)
        self.assertIsNone(config['target'].arch)
        self.assertFalse(config['target'].files)

        # Should be empty when no target is specified
        self.assertFalse(config['processes'])
        self.assertFalse(config['modules'])

        # An empty project with no target will have no arguments
        self.assertFalse(config['target'].args.get_resolved_args(''))
        self.assertFalse(config['target'].args.symbolic_files)
        self.assertFalse(config['sym_args'])

        # Disabled by default
        self.assertFalse(config['enable_pov_generation'])
        self.assertFalse(config['use_seeds'])
        self.assertFalse(config['use_recipes'])
        self.assertFalse(config['use_fault_injection'])

    def test_cat_x86_concrete_project_config(self):
        """
        Test Linux project creation given a x86 binary (``cat``) and nothing
        else. No image, project name, symbolic arguments, etc. are provided.
        """
        target, cls = target_from_file(CAT_X86_PATH)
        project = monkey_patch_project(cls(), LINUX_IMAGE_DESC)

        config = project._configure(target)

        self._assert_cat_x86_common(config)

        # No target arguments specified
        self.assertFalse(config['target'].args.get_resolved_args(''))
        self.assertFalse(config['target'].args.symbolic_files)
        self.assertFalse(config['sym_args'])

        # Disabled by default
        self.assertFalse(config['enable_pov_generation'])
        self.assertFalse(config['use_seeds'])
        self.assertFalse(config['use_recipes'])
        self.assertFalse(config['use_fault_injection'])

    def test_cat_x86_symbolic_project_config(self):
        """
        Test Linux project creation given a x86 binary (``cat``) and a symbolic
        file argument.
        """
        target, cls = target_from_file(CAT_X86_PATH)
        target.args = ['-T', '@@']
        project = monkey_patch_project(cls(), LINUX_IMAGE_DESC)

        config = project._configure(target)

        self._assert_cat_x86_common(config)

        # Verify symbolic arguments
        self.assertListEqual(config['target'].args.raw_args, ['-T', 'input-0'])
        self.assertListEqual(config['target'].args.get_resolved_args(''), ['-T', 'input-0'])
        self.assertFalse(config['sym_args'])
        self.assertTrue(config['target'].args.symbolic_files)

        # Disabled by default
        self.assertFalse(config['enable_pov_generation'])
        self.assertFalse(config['use_seeds'])
        self.assertFalse(config['use_recipes'])
        self.assertFalse(config['use_fault_injection'])

    def _assert_cat_x86_common(self, config):
        """Assert common properties for the x86 ``cat`` project."""
        # Assert that we have actually created a Linux project
        self.assertEqual(config['project_type'], 'linux')

        # Assert that the target is the one given (cat)
        self.assertEqual(config['target'].path, CAT_X86_PATH)
        self.assertEqual(config['target'].arch, 'i386')
        self.assertListEqual(config['target'].files, [CAT_X86_PATH])
        self.assertListEqual(config['processes'], [CAT_X86])
        self.assertListEqual(config['modules'], [(CAT_X86, False)])

        # Assert that the x86 Linux image was selected
        self.assertDictEqual(config['image'], LINUX_IMAGE_DESC)

        # Verify static analysis results
        self.assertTrue(config['dynamically_linked'])
        self.assertCountEqual(config['modelled_functions'],
                              [u'strncmp', u'printf', u'memcpy', u'strcpy',
                               u'fprintf', u'memcmp', u'strlen', u'strcmp'])

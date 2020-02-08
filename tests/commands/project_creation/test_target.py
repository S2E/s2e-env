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
from unittest import TestCase

from s2e_env.commands.project_creation import CGCProject
from s2e_env.commands.project_creation import LinuxProject
from s2e_env.commands.project_creation import WindowsProject, \
        WindowsDLLProject, WindowsDriverProject
from s2e_env.commands.project_creation import Target

from . import DATA_DIR


class TargetTestCase(TestCase):
    def test_cgc_target(self):
        """Test CGC executable target."""
        target_path = os.path.join(DATA_DIR, 'CADET_00001')
        target = Target.from_file(target_path)

        self.assertEqual(target.path, target_path)
        self.assertEqual(target.arch, 'i386')
        self.assertEqual(target.operating_system, 'decree')
        self.assertFalse(target.aux_files)
        self.assertIsInstance(target.initialize_project(), CGCProject)
        self.assertFalse(target.is_empty())

    def test_empty_cgc_target(self):
        """Test empty CGC target."""
        target = Target.empty(CGCProject)

        self.assertFalse(target.path)
        self.assertFalse(target.arch)
        self.assertFalse(target.operating_system)
        self.assertFalse(target.aux_files)
        self.assertIsInstance(target.initialize_project(), CGCProject)
        self.assertTrue(target.is_empty())

    def test_linux_i386_target(self):
        """Test Linux i386 executable target."""
        target_path = os.path.join(DATA_DIR, 'cat')
        target = Target.from_file(target_path)

        self.assertEqual(target.path, target_path)
        self.assertEqual(target.arch, 'i386')
        self.assertEqual(target.operating_system, 'linux')
        self.assertFalse(target.aux_files)
        self.assertIsInstance(target.initialize_project(), LinuxProject)
        self.assertFalse(target.is_empty())

    def test_windows_x86_64_target(self):
        """Test Windows x86_64 executable target."""
        target_path = os.path.join(DATA_DIR, 'scanuser.exe')
        target = Target.from_file(target_path)

        self.assertEqual(target.path, target_path)
        self.assertEqual(target.arch, 'x86_64')
        self.assertEqual(target.operating_system, 'windows')
        self.assertFalse(target.aux_files)
        self.assertIsInstance(target.initialize_project(), WindowsProject)
        self.assertFalse(target.is_empty())

    def test_windows_x86_64_dll_target(self):
        """Test Windows x86_64 DLL target."""
        target_path = os.path.join(DATA_DIR, 'myputs.dll')
        target = Target.from_file(target_path)

        self.assertEqual(target.path, target_path)
        self.assertEqual(target.arch, 'x86_64')
        self.assertEqual(target.operating_system, 'windows')
        self.assertFalse(target.aux_files)
        self.assertIsInstance(target.initialize_project(), WindowsDLLProject)
        self.assertFalse(target.is_empty())

    def test_windows_x86_64_sys_target(self):
        """Test Windows x86_64 SYS driver target."""
        target_path = os.path.join(DATA_DIR, 'scanner.sys')
        target = Target.from_file(target_path)

        self.assertEqual(target.path, target_path)
        self.assertEqual(target.arch, 'x86_64')
        self.assertEqual(target.operating_system, 'windows')
        self.assertFalse(target.aux_files)
        self.assertIsInstance(target.initialize_project(), WindowsDriverProject)
        self.assertFalse(target.is_empty())

    def test_windows_x86_64_inf_target(self):
        """Test Windows x86_64 INF driver target."""
        target_path = os.path.join(DATA_DIR, 'scanner.inf')
        target = Target.from_file(target_path)

        self.assertEqual(target.path, target_path)
        self.assertEqual(target.arch, 'x86_64')
        self.assertEqual(target.operating_system, 'windows')
        self.assertCountEqual(target.aux_files,
                              [os.path.join(DATA_DIR, 'scanner.sys'),
                               os.path.join(DATA_DIR, 'scanuser.exe')])
        self.assertIsInstance(target.initialize_project(), WindowsDriverProject)
        self.assertFalse(target.is_empty())

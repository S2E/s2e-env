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

from s2e_env.analysis.elf import ELFAnalysis


CAT_X86_PATH = os.path.join(os.path.dirname(__file__), '..', 'dat', 'cat')


class ELFTestCase(TestCase):
    def test_cat_x86(self):
        """Test analysis of dynamically-linked x86 ELF executable."""
        with ELFAnalysis(CAT_X86_PATH) as elf:
            self.assertTrue(elf.is_dynamically_linked())

            self.assertCountEqual(elf.get_modelled_functions(),
                                  [u'strncmp', u'printf', u'memcpy', u'strcpy',
                                   u'fprintf', u'memcmp', u'strlen', u'strcmp'])

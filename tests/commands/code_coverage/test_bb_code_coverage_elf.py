"""
Copyright (c) 2021 Bradley Morgan

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

import os, json, itertools
from unittest import TestCase

from s2e_env.commands.code_coverage import basic_block

from . import CURR_DIR

class ELFTestCase(TestCase):
    def test_bb_cov(self):
        """Test basic block code coverage of an x86 ELF executable, mmount"""
        bbs = tb_coverage = None

        with open(os.path.join(CURR_DIR, 'mmount_bbs.json'), 'r') as f1:
            bbs = json.load(f1, cls=basic_block.BasicBlockDecoder)
        with open(os.path.join(CURR_DIR, 'mmount_tb_coverage.json'), 'r') as f2:
            tb_coverage = json.load(f2)

        bb_coverage = basic_block._get_basic_block_coverage(tb_coverage, bbs)

        total_bbs = len(bbs)
        num_covered_bbs = len(set(itertools.chain(*iter(bb_coverage.values()))))

        self.assertEqual(total_bbs, 1536)
        self.assertEqual(num_covered_bbs, 5)
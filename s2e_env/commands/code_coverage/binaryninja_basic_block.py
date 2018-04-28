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


import importlib
import logging
import os
import sys

from s2e_env.command import CommandError
from .basic_block import BasicBlock, BasicBlockCoverage


logger = logging.getLogger('basicblock')


class BinaryNinjaBasicBlockCoverage(BasicBlockCoverage):
    """
    Generate basic block coverage report using Binary Ninja as the disassembler
    backend. This requires the professional version of Binary Ninja to use the
    headless API.
    """

    def __init__(self):
        super(BinaryNinjaBasicBlockCoverage, self).__init__()

        self._bv = None
        self._binaryninja_mod = None

    def _initialize_disassembler(self):
        """
        Initialize the Binary Ninja Python API.
        """
        binaryninja_dir = self.config.get('binary_ninja', {}).get('dir')
        if not binaryninja_dir:
            raise CommandError('No path to Binary Ninja has been given in '
                               's2e.yaml. Please add the following to your '
                               's2e.yaml config to use this disassembler '
                               'backend:\n\n'
                               'binary_ninja:\n'
                               '\tdir: /path/to/binaryninja')

        binaryninja_py_dir = os.path.join(binaryninja_dir, 'python')
        if not os.path.isdir(binaryninja_py_dir):
            raise CommandError('Binary Ninja not found at %s' % binaryninja_dir)

        sys.path.append(binaryninja_py_dir)
        self._binaryninja_mod = importlib.import_module('binaryninja')

    def _get_disassembly_info(self, module_path):
        """
        Extract disassembly information from the target binary using Binary
        Ninja.
        """
        logger.info('Generating disassembly information from Binary Ninja for '
                    '%s', module_path)

        self._bv = self._binaryninja_mod.BinaryViewType.get_view_of_file(module_path)

        # Get basic blocks
        bbs = []
        for func in self._bv.functions:
            for basic_block in func.basic_blocks:
                split_bbs = self._split_basic_block(func.name, basic_block)
                bbs.extend(split_bbs)

        # Get the module's base address
        base_addr = self._bv.start

        # Get the module's end address
        end_addr = self._bv.end

        return BasicBlockCoverage._make_disassembly_info(bbs, base_addr, end_addr)

    def _split_basic_block(self, func_name, basic_block):
        """
        Splits a single basic block into multiple basic blocks so that function
        calls are considered basic block boundaries.

        E.g. If a basic block contains a single function call, this block will
        be split into two blocks - the first ending with the function call and
        the second block starting from the instruction immediately following
        the function call (i.e. the function call's return address).

        Args:
            func_name: Name of the function.
            basic_block: A ``binaryninja.basicblock.BasicBlock`` object.

        Returns:
            A list of ``BasicBlock`` objects.
        """
        split_bbs = []
        inst_addrs = [inst.address for inst in basic_block.disassembly_text]
        num_insts = len(inst_addrs)
        bb_start_addr = basic_block.start
        bb_end_addr = basic_block.end

        # This lambda is used to retrieve the abstracted instruction type at a
        # given address. This is so that we don't have to deal with the various
        # call instructions that may be used in the underlying architecture
        get_op = lambda addr: basic_block.function.get_low_level_il_at(addr).operation

        for i, addr in enumerate(inst_addrs):
            op = get_op(addr)
            if op == self._binaryninja_mod.enums.LowLevelILOperation.LLIL_CALL and i < num_insts - 1:
                bb_end_addr = inst_addrs[i + 1] + self._bv.get_instruction_length(addr)
                split_bbs.append(BasicBlock(bb_start_addr, bb_end_addr, func_name))
                bb_start_addr = inst_addrs[i + 1]

        if bb_start_addr < bb_end_addr:
            split_bbs.append(BasicBlock(bb_start_addr, bb_end_addr, func_name))

        return split_bbs

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


import logging

from s2e_env.command import CommandError
from .basic_block import BasicBlock, BasicBlockCoverage


logger = logging.getLogger('basicblock')


def _split_basic_block(func_name, basic_block):
    """
    Splits a single basic block into multiple basic blocks so that function
    calls are considered basic block boundaries.

    E.g. If a basic block contains a single function call, this block will be
    split into two blocks - the first ending with the function call and the
    second block starting from the instruction immediately following the
    function call (i.e. the function call's return address).

    Args:
        func_name: Name of the function.
        basic_block: Dictionary containing Radare's basic block information.

    Returns:
        A list of ``BasicBlock`` objects.
    """
    split_bbs = []
    insts = basic_block['ops']
    num_insts = len(insts)
    bb_start_addr = basic_block['offset']
    bb_end_addr = bb_start_addr + basic_block['size']

    for i, inst in enumerate(insts):
        if inst['type'] == 'call' and i < num_insts - 1:
            bb_end_addr = inst['offset'] + inst['size']
            split_bbs.append(BasicBlock(bb_start_addr, bb_end_addr, func_name))
            bb_start_addr = insts[i + 1]

    if bb_start_addr < bb_end_addr:
        split_bbs.append(BasicBlock(bb_start_addr, bb_end_addr, func_name))

    return split_bbs


class R2BasicBlockCoverage(BasicBlockCoverage):
    """
    Generate basic block coverage report using Radare2 as the disassembler
    backend.
    """

    def __init__(self):
        super(R2BasicBlockCoverage, self).__init__()

        self._r2 = None

    def _initialize_disassembler(self):
        """
        Initialize Radare2 with r2pipe and perform the initial analysis.

        Sets the ``_r2`` attribute or raises an exception if Radare2/r2pipe
        cannot be found.
        """
        try:
            import r2pipe
        except ImportError:
            raise CommandError('Unable to load r2pipe. Is Radare2/r2pipe '
                               'installed?')

        self._r2 = r2pipe.open(self._project_desc['target_path'])
        self._r2.cmd('aaa')

    def _get_basic_blocks(self):
        """
        Extract basic block information from the target binary using Radare2.
        """
        logger.info('Generating basic block information from Radare')

        bbs = []
        for func in self._r2.cmdj('aflj'):
            func_name = func['name']
            func_graph = self._r2.cmdj('agj 0x%x' % func['offset'])

            if not func_graph:
                logger.warn('Function %s has an empty graph. Skipping...', func_name)
                continue

            # For some reason Radare returns the function graph in a list with
            # 1 element. Unwrap this list
            func_graph = func_graph[0]

            for basic_block in func_graph['blocks']:
                # Split the basic blocks so that function calls are considered
                # basic block boundaries
                split_bbs = _split_basic_block(func_name, basic_block)
                bbs.extend(split_bbs)

        return bbs

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


from __future__ import division

from collections import defaultdict, namedtuple
import json
import itertools
import logging
import os

from s2e_env.command import ProjectCommand, CommandError
from . import get_tb_files, get_tb_state, parse_tb_file


logger = logging.getLogger('basicblock')


BasicBlock = namedtuple('BasicBlock', ['start_addr', 'end_addr', 'function'])


class BasicBlockCoverage(ProjectCommand):
    """
    Generate a basic block coverage report.

    This subcommand requires one of IDA Pro, Radare2 or Binary Ninja to use as
    a disassembler.
    """

    help = 'Generate a basic block coverage report. This requires IDA Pro, '  \
           'Radare2 or Binary Ninja as a disassembler.'

    RESULTS = 'Basic block coverage saved to {bb_file}\n\n'             \
              'Statistics\n'                                            \
              '==========\n\n'                                          \
              'Total basic blocks: {num_bbs}\n'                         \
              'Covered basic blocks: {num_covered_bbs} ({percent:.1%})'

    def handle(self, *args, **options):
        # Get translation block coverage information
        target_path = self._project_desc['target_path']
        target_dir = os.path.dirname(target_path)
        modules = self._project_desc['modules']

        for module_info in modules:
            module = module_info[0]
            module_path = os.path.join(target_dir, module)

            # Initialize the backend disassembler
            self._initialize_disassembler(module_path)

            # Get static basic block information from the binary
            bbs = self._get_basic_blocks(module_path)
            if not bbs:
                raise CommandError('No basic block information found')

            # Calculate basic block coverage information (based on the
            # translation block coverage recorded by S2E)
            bb_coverage = self._get_basic_block_coverage(module, bbs)
            if not bb_coverage:
                raise CommandError('No basic block coverage information found')

            # Calculate some statistics (across all states)
            total_bbs = len(bbs)
            num_covered_bbs = len(set(itertools.chain(*bb_coverage.values())))

            # Write the basic block information to a JSON file
            bb_coverage_file = self._save_basic_block_coverage(module,
                                                               bb_coverage,
                                                               total_bbs,
                                                               num_covered_bbs)

            return self.RESULTS.format(bb_file=bb_coverage_file,
                                       num_bbs=total_bbs,
                                       num_covered_bbs=num_covered_bbs,
                                       percent=num_covered_bbs / total_bbs)

    def _initialize_disassembler(self, module_path):
        """
        Initialize the backend disassembler.
        """
        pass

    def _get_basic_blocks(self, module_path):
        """
        Extract basic block information from the target binary using one of the
        disassembler backends (IDA Pro, Radare2 or Binary Ninja).

        Returns:
            A list of ``BasicBlock``s, i.e. named tuples containing:
                1. Basic block start address
                2. Basic block end address
                3. Name of function that the basic block resides in
        """
        raise NotImplementedError('subclasses of BasicBlockCoverage must '
                                  'provide a _get_basic_blocks() method')

    def _get_basic_block_coverage(self, target_name, basic_blocks):
        """
        Calculate the basic block coverage.

        This information is derived from the static basic block list (generated
        by the chosen disassembler) and the translation block (TB) list
        (extracted from the JSON file(s) generated by S2E's
        ``TranslationBlockCoverage`` plugin).
        """
        tb_coverage_files = get_tb_files(self.project_path('s2e-last'))
        covered_bbs = defaultdict(set)

        for tb_coverage_file in tb_coverage_files:
            tb_coverage_data = parse_tb_file(tb_coverage_file, target_name)
            if not tb_coverage_data:
                continue

            state = get_tb_state(tb_coverage_file)

            logger.info('Calculating basic block coverage for state %d', state)
            for tb_start_addr, tb_end_addr, _ in tb_coverage_data:
                for bb in basic_blocks:
                    # Check if the translation block falls within a basic block
                    # OR a basic block falls within a translation block
                    if (bb.end_addr >= tb_start_addr >= bb.start_addr or
                            bb.start_addr <= tb_end_addr <= bb.end_addr):
                        covered_bbs[state].add(bb)

        return covered_bbs

    def _save_basic_block_coverage(self, module, basic_blocks, total_bbs, num_covered_bbs):
        """
        Write the basic block coverage information to a single JSON file. This
        JSON file will contain the aggregate basic block coverage information
        across **all** states.

        Args:
            module: Name of the module that basic block coverage has been
            generated for.
            basic_blocks: Dictionary mapping state IDs to covered basic blocks.
            total_bbs: The total number of basic blocks in the program.
            num_covered_bbs: The number of basic blocks covered by S2E.

        Returns:
            The path of the JSON file.
        """
        bb_coverage_file = self.project_path('s2e-last',
                                             '%s_coverage.json' % module)

        logger.info('Saving basic block coverage to %s', bb_coverage_file)

        to_dict = lambda bb: {'start_addr': bb.start_addr,
                              'end_addr': bb.end_addr,
                              'function': bb.function}
        bbs_json = {
            'stats': {
                'total_basic_blocks': total_bbs,
                'covered_basic_blocks': num_covered_bbs,
            },
            'coverage': [to_dict(bb) for bbs in basic_blocks.values() for bb in bbs],
        }

        with open(bb_coverage_file, 'w') as f:
            json.dump(bbs_json, f)

        return bb_coverage_file

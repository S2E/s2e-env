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

from collections import defaultdict
import json
import itertools
import logging
import os

from s2e_env.command import ProjectCommand, CommandError
from . import get_tb_files, get_tb_state, parse_tb_file


logger = logging.getLogger('basicblock')


class BasicBlock(object):
    """
    Immutable basic block representation.
    """

    def __init__(self, start_addr, end_addr, function):
        self._start_addr = start_addr
        self._end_addr = end_addr
        self._function = function

    @property
    def start_addr(self):
        return self._start_addr

    @property
    def end_addr(self):
        return self._end_addr

    @property
    def function(self):
        return self._function


class BasicBlockEncoder(json.JSONEncoder):
    """
    Encodes a ``BasicBlock`` object in JSON format.
    """

    # pylint: disable=method-hidden
    def default(self, o):
        if isinstance(o, BasicBlock):
            return {
                'start_addr': o.start_addr,
                'end_addr': o.end_addr,
                'function': o.function,
            }

        return super(BasicBlockEncoder, self).default(o)


class BasicBlockDecoder(json.JSONDecoder):
    """
    Decodes a ``BasicBlock`` object from JSON format.
    """

    def __init__(self, *args, **kwargs):
        super(BasicBlockDecoder, self).__init__(object_hook=self.object_hook,
                                                *args, **kwargs)

    # pylint: disable=method-hidden
    def object_hook(self, d):
        if 'start_addr' in d:
            return BasicBlock(d['start_addr'], d['end_addr'], d['function'])

        return d


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
        # Initialize the backend disassembler
        self._initialize_disassembler()

        target_path = self._project_desc['target_path']
        target_dir = os.path.dirname(target_path)
        modules = self._project_desc['modules']

        # Get translation block coverage information for each module
        for module, _ in modules:
            # Check if a cached version of the disassembly information exists.
            # If it does, then we don't have to disassemble the binary (which
            # may take a long time for large binaries)
            disas_info = self._get_cached_disassembly_info(module)

            # If no cached .disas file exists, generate a new one using the
            # given disassembler and cache the results
            if not disas_info:
                module_path = os.path.join(target_dir, module)
                disas_info = self._get_disassembly_info(module_path)
                if not disas_info:
                    raise CommandError('No disassembly information found')

                self._save_disassembly_info(module, disas_info)

            # Calculate basic block coverage information (based on the
            # translation block coverage recorded by S2E)
            bbs = disas_info.get('bbs', [])
            bb_coverage = self._get_basic_block_coverage(module, bbs)
            if not bb_coverage:
                raise CommandError('No basic block coverage information found')

            # Calculate some statistics (across all states)
            total_bbs = len(bbs)
            num_covered_bbs = len(set(itertools.chain(*bb_coverage.values())))

            # Write the basic block coverage information to disk.
            #
            # Combine all the basic block coverage information (across all
            # states) into a single JSON file.
            bb_coverage_file = self._save_basic_block_coverage(module,
                                                               bb_coverage,
                                                               total_bbs,
                                                               num_covered_bbs)

            logger.success(self.RESULTS.format(bb_file=bb_coverage_file,
                                               num_bbs=total_bbs,
                                               num_covered_bbs=num_covered_bbs,
                                               percent=num_covered_bbs / total_bbs))

    def _initialize_disassembler(self):
        """
        Initialize the backend disassembler.
        """
        pass

    def _get_disassembly_info(self, module_path):
        """
        Disassemble the give module using on the of the supported backends (IDA
        Pro, Radare2 or Binary Ninja) and extract useful information, such as
        basic block information and module start/end addresses.

        Returns:
            A ``dict`` containing disassembly information.
        """
        raise NotImplementedError('subclasses of BasicBlockCoverage must '
                                  'provide a _get_disassembly_info method')

    def _get_cached_disassembly_info(self, module):
        """
        Check if the disassembly information from the target binary has already
        been generated (in a .disas file). If it has, reuse this information.

        The .disas file is just a JSON dump.

        Returns:
            A ``dict`` containing the disassembly information. If no .disas
            file exists, ``None`` is returned.
        """
        logger.info('Checking for existing .disas file')

        disas_path = self.project_path('%s.disas' % module)
        if not os.path.isfile(disas_path):
            logger.info('No .disas file found')
            return None

        # Force a new .disas to be generated if the target binary has a newer
        # modification time compared to the .disas file

        disas_mtime = os.path.getmtime(disas_path)
        target_mtime = os.path.getmtime(self._project_desc['target_path'])

        if disas_mtime < target_mtime:
            logger.info('%s is out of date. A new .disas file will be generated',
                        disas_path)
            return None

        logger.info('%s found. Returning cached basic blocks', disas_path)

        with open(disas_path, 'r') as disas_file:
            return json.load(disas_file, cls=BasicBlockDecoder)

    def _save_disassembly_info(self, module, disas_info):
        """
        Save the disassembly information to a .disas file in the project
        directory.

        The .disas file is just a JSON dump.

        Args:
            module: Name of the module for the disassembly information in
            ``disas_info``.
            disas_info: A dictionary containing the disassemly information.
        """
        disas_path = self.project_path('%s.disas' % module)

        logger.info('Saving disassembly information to %s', disas_path)

        with open(disas_path, 'w') as disas_file:
            json.dump(disas_info, disas_file, cls=BasicBlockEncoder)

    def _get_basic_block_coverage(self, module, bbs):
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
            tb_coverage_data = parse_tb_file(tb_coverage_file, module)
            if not tb_coverage_data:
                continue

            state = get_tb_state(tb_coverage_file)

            logger.info('Calculating basic block coverage for state %d', state)

            for tb_start_addr, tb_end_addr, _ in tb_coverage_data:
                for bb in bbs:
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

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
        # Get translation block coverage information
        target_path = self._project_desc['target_path']
        target_dir = os.path.dirname(target_path)
        modules = self._project_desc['modules']

        for module, _ in modules:
            module_path = os.path.join(target_dir, module)

            # Initialize the backend disassembler
            self._initialize_disassembler(module_path)

            # Check if a cached version of the basic block information exists.
            # If it does, then we don't have to disassemble the binary (which
            # may take a long time for large binaries)
            bbs = self._get_cached_basic_blocks(module)

            # If no cached .bblist file exists, generate a new one using the
            # given disassembler and cache the results
            if not bbs:
                bbs = self._get_basic_blocks(module_path)
                if not bbs:
                    raise CommandError('No basic block information found')

                self._save_basic_blocks(module, bbs)

            # Calculate basic block coverage information (based on the
            # translation block coverage recorded by S2E)
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

    def _initialize_disassembler(self, module_path):
        """
        Initialize the backend disassembler.
        """
        pass

    def _get_cached_basic_blocks(self, module):
        """
        Check if the basic block information from the target binary has already
        been generated (in a .bblist file). If it has, reuse this information.

        The .bblist file is just a JSON dump.

        Returns:
            A list of ``BasicBlock`` objects read from a .bblist file. If no
            .bblist file exists, ``None`` is returned.
        """
        logger.info('Checking for existing .bblist file')

        bblist_path = self.project_path('%s.bblist' % module)

        if not os.path.isfile(bblist_path):
            logger.info('No .bblist file found')
            return None

        # Force a new .bblist to be generated if the target binary has a newer
        # modification time compared to the .bblist file

        bblist_mtime = os.path.getmtime(bblist_path)
        target_mtime = os.path.getmtime(self._project_desc['target_path'])

        if bblist_mtime < target_mtime:
            logger.info('%s is out of date. A new .bblist file will be generated',
                        bblist_path)
            return None

        logger.info('%s found. Returning cached basic blocks', bblist_path)

        with open(bblist_path, 'r') as bblist_file:
            return json.load(bblist_file, cls=BasicBlockDecoder)

    def _get_basic_blocks(self, module_path):
        """
        Extract basic block information from the target binary using one of the
        disassembler backends (IDA Pro, Radare2 or Binary Ninja).

        Returns:
            A list of ``BasicBlock`` objects.
        """
        raise NotImplementedError('subclasses of BasicBlockCoverage must '
                                  'provide a _get_basic_blocks() method')

    def _save_basic_blocks(self, module, bbs):
        """
        Save the a list of basic blocks to a .bblist file in the project
        directory.

        The .bblist file is just a JSON dump.

        Args:
            module: Name of the module for the basic blocks in ``bbs``.
            bbs: A list of ``BasicBlock`` objects.
        """
        bblist_path = self.project_path('%s.bblist' % module)

        logger.info('Saving basic block information to %s', bblist_path)

        with open(bblist_path, 'w') as bblist_file:
            json.dump(bbs, bblist_file, cls=BasicBlockEncoder)

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

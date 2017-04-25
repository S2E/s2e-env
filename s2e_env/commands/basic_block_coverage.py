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


from collections import namedtuple
import glob
import json
import os
import shutil

import sh
from sh import ErrorReturnCode

from s2e_env import CONSTANTS, YAML_CONFIG_PATH
from s2e_env.command import ProjectCommand, CommandError

try:
    from tempfile import TemporaryDirectory
except ImportError:
    from s2e_env.utils.tempdir import TemporaryDirectory


BasicBlock = namedtuple('BasicBlock', ['start_addr', 'end_addr', 'function'])
TranslationBlock = namedtuple('TranslationBlock', ['start_addr', 'end_addr'])


class Command(ProjectCommand):
    """
    Generate a basic block coverage report.

    This subcommand requires IDA Pro.
    """

    help = 'Generate a basic block coverage report. This requires IDA Pro.'

    def handle(self, *args, **options):
        # Determine the IDA Pro path and check that it is valid
        ida_path = self._get_ida_path()
        if not os.path.isfile(ida_path):
            raise CommandError('IDA Pro not found at %s' % ida_path)

        # Change into the project directory
        os.chdir(self._project_dir)

        # Get the basic block information
        bbs = self._get_basic_blocks(ida_path)

        # Get translation block coverage information
        tbs = self._get_tb_coverage()

        # Calculate the basic block coverage information
        bb_coverage = self._basic_block_coverage(bbs, tbs)

        # Write the basic block information to a JSON file
        self._save_basic_block_coverage(bb_coverage)

    def _get_ida_path(self):
        """
        Determine which version of IDA to use based on the project's
        architecture (32 or 64 bit).

        Returns the path to IDA Pro or raises an exception if it cannot be
        found.
        """
        ida_dir = CONSTANTS['ida']['dir']
        if not ida_dir:
            raise CommandError('No path to IDA has been given in %s. IDA is '
                               'required to generate a basic block coverage '
                               'report' % YAML_CONFIG_PATH)

        project_arch = self._project_desc['arch']
        if project_arch == 'i386':
            ida_path = os.path.join(ida_dir, 'idal')
        elif project_arch == 'x86_64':
            ida_path = os.path.join(ida_dir, 'idal64')
        else:
            raise CommandError('Invalid project architecture \'%s\' - unable '
                               'to determine the version of IDA Pro to use' %
                               project_arch)

        return ida_path

    def _get_basic_blocks(self, ida_path):
        """
        Extract basic block information from the target binary using S2E's IDA
        Pro script.

        This extraction is done within a temporary directory so that we don't
        pollute the file system with temporary idbs and other such things.

        Args:
            ida_path: Path to the IDA Pro executable.

        Returns:
            A list of ``BasicBlock``s, i.e. named tuples containing:
                1. Basic block start address
                2. Basic block end address
                3. Name of function that the basic block resides in
        """
        self.info('Generating basic block information from IDA Pro')

        try:
            with TemporaryDirectory() as temp_dir:
                # Copy the binary to the temporary directory. Because projects
                # are created with a symlink to the target program, then IDA
                # Pro will generate the idb and bblist files in the symlinked
                # target's directory. Which is not what we want
                target_path = self._project_desc['target']
                target_name = os.path.basename(target_path)

                temp_target_path = os.path.join(temp_dir, target_name)
                shutil.copyfile(target_path, temp_target_path)

                # Run the IDA Pro extractBasicBlocks script
                env_vars = os.environ.copy()
                env_vars['TVHEADLESS'] = '1'

                ida = sh.Command(ida_path)
                ida('-A', '-B',
                    '-S%s' % self.install_path('bin', 'extractBasicBlocks.py'),
                    temp_target_path, _out=os.devnull, _tty_out=False,
                    _cwd=temp_dir, _env=env_vars)

                # Check that the basic block list file was correctly generated
                bblist_file = os.path.join(temp_dir, '%s.bblist' % target_name)
                if not os.path.isfile(bblist_file):
                    raise CommandError('Failed to generate bblist file for '
                                       '%s' % target_name)

                # Parse the basic block list file
                #
                # to_basic_block takes a 3-tuple read from the bblist file and
                # converts it to a BasicBlock
                to_basic_block = lambda tup: BasicBlock(int(tup[0], 16),
                                                        int(tup[1], 16),
                                                        tup[2])
                with open(bblist_file, 'r') as f:
                    return [to_basic_block(l.rstrip().split(' ')) for l in f]
        except ErrorReturnCode as e:
            raise CommandError(e)

    def _get_tb_coverage(self):
        """
        Extract translation block (TB) coverage from the JSON files generated
        by the ``TranslationBlockCoverage`` plugin.

        Returns:
            A list of ``TranslationBlock``'s, i.e. named tuples containing:
                1. Translation block start address
                2. Translation block end address
        """
        self.info('Generating translation block coverage information')

        target_path = self._project_desc['target']
        target_name = os.path.basename(target_path)

        tb_coverage_files = glob.glob(os.path.join(self._project_dir,
                                                   's2e-last', '*',
                                                   'tbcoverage-*.json'))
        if not tb_coverage_files:
            self.warn('No translation block coverage files found in s2e-last. '
                      'Did you enable the ``TranslationBlockCoverage`` plugin '
                      'in s2e-config.lua?')
            return

        covered_tbs = set()
        for tb_coverage_file in tb_coverage_files:
            with open(tb_coverage_file, 'r') as f:
                try:
                    tb_coverage_data = json.load(f)
                except Exception:
                    self.warn('Failed to parse translation block JSON file '
                              '%s' % tb_coverage_file)
                    continue
            if target_name not in tb_coverage_data:
                self.warn('Target %s not found in translation block JSON file '
                          '%s. Skipping...' % (target_name, tb_coverage_file))

            covered_tbs.update(TranslationBlock(start_addr, end_addr) for
                               start_addr, end_addr, _ in
                               tb_coverage_data[target_name])

        return list(covered_tbs)

    def _basic_block_coverage(self, basic_blocks, translation_blocks):
        """
        Calculate the basic block coverage.

        This information is derived from the basic block list (generated by IDA
        Pro) and the translation block list (generated by S2E's
        ``TranslationBlockCoverage``).

        Args:
            basic_blocks: List of basic blocks.
            translation_blocks: List of executed translation blocks.

        Returns:
            A list of ``BasicBlock``s executed by S2E.
        """
        self.info('Calculating basic block coverage')

        # Naive approach :(
        covered_bbs = set()
        for tb_start_addr, tb_end_addr in translation_blocks:
            for bb in basic_blocks:
                # Check if the translation block falls within a basic block OR
                # a basic block falls within a translation block
                if (bb.end_addr >= tb_start_addr >= bb.start_addr or
                        bb.start_addr <= tb_end_addr <= bb.end_addr):
                    covered_bbs.add(bb)

        return list(covered_bbs)

    def _save_basic_block_coverage(self, basic_blocks):
        """
        Write the basic block coverage information to a JSON file.
        """
        bb_coverage_file = os.path.join(self._project_dir,
                                        'basic_block_coverage.json')

        self.info('Saving basic block coverage to %s' % bb_coverage_file)

        to_dict = lambda bb: {'start_addr': bb.start_addr,
                              'end_addr': bb.end_addr,
                              'function': bb.function}
        bbs_json = [to_dict(bb) for bb in basic_blocks]

        with open(bb_coverage_file, 'w') as f:
            json.dump(bbs_json, f)

        self.success('Basic block coverage saved to %s' % bb_coverage_file)

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


import glob
import json
import os

from elftools.elf.elffile import ELFFile
from elftools.dwarf import constants as dwarf_consts

from s2e_env.command import ProjectCommand, CommandError


def _get_file_line_coverage(target_path, addr_counts):
    """
    Map addresses to line numbers in the source code file.

    Args:
        target_path: Path to the analysis target.
        addr_counts: A dictionary mapping instruction addresses exuected by S2E
                     (and recorded by the ``TranslationBlockCoverage`` plugin)
                     to the number of times they were executed.

    Returns:
        A dictionary that maps source code files to line numbers and the number
        of times each line was executed.

        E.g.:
            ```
            {
                'path/to/source': {
                                      1: 2, # Line 1 was executed twice
                                      2: 5, # Line 2 was executed five times
                                      ...
                                  },
                ...
            }
            ```
    """
    file_line_info = {}

    with open(target_path, 'r') as f:
        elf = ELFFile(f)

        if not elf.has_dwarf_info():
            raise CommandError('%s has no DWARF info' % target_path)

        dwarf_info = elf.get_dwarf_info()

        # Adapted from readelf.py:
        #   https://github.com/eliben/pyelftools/blob/master/scripts/readelf.py
        for cu in dwarf_info.iter_CUs():
            line_program = dwarf_info.line_program_for_CU(cu)

            cu_filepath = line_program['file_entry'][0].name

            if line_program['include_directory']:
                dir_index = line_program['file_entry'][0].dir_index
                if dir_index > 0:
                    dir_ = line_program['include_directory'][dir_index - 1]
                else:
                    dir_ = '.'
                cu_filepath = os.path.join(dir_, cu_filepath)

                # The actual source path depends on the DWARF line info state
                # machine
                src_path = cu_filepath
                for entry in line_program.get_entries():
                    state = entry.state

                    if state is None:
                        # Special handling for commands that don't set a new
                        # state
                        if entry.command == dwarf_consts.DW_LNS_set_file:
                            file_entry = \
                                line_program['file_entry'][entry.args[0] - 1]
                            if file_entry.dir_index == 0:
                                # Current directory
                                src_path = os.path.join('.', file_entry.name)
                            else:
                                include_dir = line_program['include_directory']
                                src_path = os.path.join(\
                                        include_dir[file_entry.dir_index - 1],
                                        file_entry.name)
                        elif entry.command == dwarf_consts.DW_LNE_define_file:
                            include_dir = line_program['include_directory']
                            src_path = include_dir[entry.args[0].dir_index]
                    elif not state.end_sequence:
                        # If this address is one that we executed in S2E, save
                        # the number of times that it was executed into the
                        # dictionary. Otherwise set it to 0
                        if src_path not in file_line_info:
                            file_line_info[src_path] = {}

                        file_line_info[src_path][state.line] = \
                                addr_counts.get(state.address, 0)

        return file_line_info


class Command(ProjectCommand):
    """
    Generate a line coverage report.

    This line coverage report is in the `lcov
    <http://ltp.sourceforge.net/coverage/lcov.php>` format, so it can be used
    to generate HTML reports.
    """

    help = 'Generates a line coverage report. Requires that the binary has ' \
           'compiled with debug information and that the source code is '    \
           'available'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('-s', '--source', required=True,
                            help='Path to the target\'s source code')

    def handle(self, *args, **options):
        source_dir = options['source']
        if not os.path.isdir(source_dir):
            raise CommandError('Source directory \'%s\' is not valid' %
                               source_dir)

        target_path = self._project_desc['target']
        target_name = os.path.basename(target_path)

        # Get the translation block coverage information
        addr_counts = self._get_addr_coverage(target_name)
        if not addr_counts:
            raise CommandError('No translation block information found')

        file_line_info = _get_file_line_coverage(target_path, addr_counts)

        self._save_coverage_info(source_dir, file_line_info)

    def _get_addr_coverage(self, target_name):
        """
        Extract address coverage from the JSON file(s) generated by the
        ``TranslationBlockCoverage`` plugin.

        Note that these addresses are an over-approximation of addresses
        actually executed because they are generated by extrapolating between
        the translation block start and end addresses. This doesn't actually
        matter, because if the address doesn't correspond to a line number in
        the DWARF information then it will just be ignored.

        Args:
            target_name: Name of the analysis target file.

        Returns:
            A dictionary mapping (over-approximated) instruction addresses
            executed by S2E to the number of times they were executed.
        """
        self.info('Generating translation block coverage information')

        # Include both multi-node and single node results
        tb_coverage_files = glob.glob(os.path.join(self._project_dir,
                                                   's2e-last', '*',
                                                   'tbcoverage-*.json')) + \
                            glob.glob(os.path.join(self._project_dir,
                                                   's2e-last',
                                                   'tbcoverage-*.json'))
        if not tb_coverage_files:
            self.warn('No translation block coverage files found in s2e-last. '
                      'Did you enable the ``TranslationBlockCoverage`` plugin '
                      'in s2e-config.lua?')

        # Get the number of times each address was executed by S2E
        addr_counts = {}
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
                continue

            for start_addr, end_addr, _ in tb_coverage_data[target_name]:
                for addr in xrange(start_addr, end_addr):
                    addr_counts[addr] = addr_counts.get(addr, 0) + 1

        return addr_counts

    def _save_coverage_info(self, source_dir, file_line_info):
        """
        Save the line coverage information in lcov format.

        The lcov format is described here:
        http://ltp.sourceforge.net/coverage/lcov/geninfo.1.php

        Args:
            source_dir: The location of the target's source code.
            file_line_info: The file line dictionary created by
                            ``_get_file_line_coverage``.
        """
        lcov_path = os.path.join(self._project_dir, 's2e-last',
                                 'coverage.info')

        self.info('Writing line coverage to %s' % lcov_path)

        with open(lcov_path, 'w') as f:
            f.write('TN:\n')
            for src_file in file_line_info.keys():
                abs_src_path = os.path.realpath(os.path.join(source_dir,
                                                             src_file))
                if not os.path.isfile(abs_src_path):
                    self.warn('Cannot find source file \'%s\'. Skipping...' %
                              abs_src_path)
                    continue

                num_non_zero_lines = 0
                num_instrumented_lines = 0

                f.write('SF:%s\n' % abs_src_path)
                for line, count in file_line_info[src_file].items():
                    f.write('DA:%d,%d\n' % (line, count))

                    if count != 0:
                        num_non_zero_lines += 1
                    num_instrumented_lines += 1
                f.write('LH:%d\n' % num_non_zero_lines)
                f.write('LF:%d\n' % num_instrumented_lines)
                f.write('end_of_record\n')

            self.success('Line coverage saved to %s' % lcov_path)

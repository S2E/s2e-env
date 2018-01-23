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


import os

from elftools.elf.elffile import ELFFile
from elftools.dwarf import constants as dwarf_consts

from s2e_env.command import CommandError


def _parse_info(dwarf_info, addr_counts):
    file_line_info = {}

    # Adapted from readelf.py (licensed under the "Unlicense"):
    #   https://github.com/eliben/pyelftools/blob/master/scripts/readelf.py
    for cu in dwarf_info.iter_CUs():
        line_program = dwarf_info.line_program_for_CU(cu)
        cu_filepath = cu.get_top_DIE().get_full_path()

        # Set the default dir and file path
        src_path = cu_filepath
        src_dir = os.path.dirname(src_path)

        for entry in line_program.get_entries():
            state = entry.state

            if state is None:
                # Special handling for commands that don't set a new
                # state
                if entry.command == dwarf_consts.DW_LNS_set_file:
                    file_entry = line_program['file_entry'][entry.args[0] - 1]
                    if not file_entry.dir_index:
                        # Current directory
                        src_path = os.path.join(src_dir, file_entry.name)
                    elif line_program['include_directory']:
                        include_dir = line_program['include_directory']
                        src_path = os.path.join(src_dir, include_dir[file_entry.dir_index - 1],
                                                file_entry.name)
                elif entry.command == dwarf_consts.DW_LNE_define_file and line_program['include_directory']:
                    include_dir = line_program['include_directory']
                    src_path = os.path.join(src_dir, include_dir[entry.args[0].dir_index])
            elif not state.end_sequence:
                # If this address is one that we executed in S2E, save
                # the number of times that it was executed into the
                # dictionary. Otherwise set it to 0
                if src_path not in file_line_info:
                    src_path = os.path.realpath(src_path)
                    file_line_info[src_path] = {}

                file_line_info[src_path][state.line] = addr_counts.get(state.address, 0)

    return file_line_info


def get_file_line_coverage(target_path, addr_counts):
    with open(target_path, 'r') as f:
        elf = ELFFile(f)

        if not elf.has_dwarf_info():
            raise CommandError('%s has no DWARF info. Please recompile with ``-g``' % target_path)

        dwarf_info = elf.get_dwarf_info()
        return _parse_info(dwarf_info, addr_counts)

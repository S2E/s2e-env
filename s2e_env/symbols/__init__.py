"""
Copyright (c) 2018-2020 Cyberhaven

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


from abc import ABCMeta, abstractmethod
import errno
import json
import logging
import os

from subprocess import Popen, PIPE

from elftools.dwarf import constants as dwarf_consts
from elftools.dwarf.descriptions import describe_form_class
from elftools.elf.elffile import ELFFile

from .debuglink import get_debug_file_for_binary
from .functions import FunctionInfo
from .lines import LineInfoEntry, LinesByAddr
from .paths import guess_target_path, guess_source_file_path

logger = logging.getLogger('symbols')


class DebugInfo(metaclass=ABCMeta):
    """
    This class abstracts away debug information for various binary file formats.
    It must be subclassed to handle specific formats (ELF, PE, etc.).
    """

    def __init__(self, path, search_paths=None):
        self._path = path
        self._search_paths = search_paths
        self._lines = LinesByAddr()
        self._funcs = FunctionInfo()

    def add(self, filename, line, addr):
        self._lines.add(filename, line, addr)

    def get(self, addr):
        """
        Return line and function information for the given address.
        This function may be overridden in case a particular debug info provider
        wants to provide line information lazily.

        :param addr: the address in the binary
        :return: a pair of LineInfoEntry, FunctionInfoEntry
        """
        sym = self._lines.get(addr)

        try:
            fcn = self._funcs.get(addr)
        except Exception:
            fcn = None

        return sym, fcn

    @property
    def path(self):
        return self._path

    def get_coverage(self, addr_counts, include_covered_files_only=False):
        if include_covered_files_only:
            for addr in addr_counts.keys():
                try:
                    self.get(addr)
                except Exception:
                    pass
        else:
            self.parse_all_info()

        file_line_info = {}

        for sym in self._lines.lines:
            if sym.filename not in file_line_info:
                file_line_info[sym.filename] = {}

            file_line_info[sym.filename][sym.line] = addr_counts.get(sym.addr, 0)

        return file_line_info

    @abstractmethod
    def parse(self):
        """
        To be implemented by clients
        """
        raise NotImplementedError('Subclasses of DebugInfo must provide a '
                                  'parse method')

    def parse_all_info(self):
        """
        To be implemented by clients that load debug info lazily
        """

    @staticmethod
    def from_file(s2e_prefix, search_paths, target_path):
        """
        Creates an instance of DebugInfo for the given binary specified in target path.

        :param search_paths: list of paths where to look for source files if the binary
        contains source line information
        :param target_path: the path to the binary
        :return: an instance of DebugInfo
        """
        errors = []
        target_path = os.path.realpath(target_path)

        logger.info('Looking for debug information in %s', target_path)

        # addrs2lines should work with PE/ELF files that contain DWARF information
        # It may not work in case there is a debug link, so pyelftools-based parser will deal with that.
        try:
            syms = Addrs2LinesDebugInfo(target_path, search_paths, s2e_prefix)
            syms.parse()
            return syms
        except Exception as e:
            logger.debug(e, exc_info=1)
            errors.append(e)

        for cls in [ELFFile]:
            try:
                syms = DwarfDebugInfo(target_path, search_paths, cls)
                syms.parse()
                return syms
            except Exception as e:
                logger.debug(e, exc_info=1)
                errors.append(e)
                errors.append(f'Could not read DWARF information from {target_path} using {cls}')

        try:
            syms = JsonDebugInfo(target_path, search_paths)
            syms.parse()
            return syms
        except Exception as e:
            logger.debug(e, exc_info=1)
            errors.append(e)
            err = 'Could not get JSON line information from %s' % target_path
            errors.append(err)

        logger.error('Could not find debug information for %s', target_path)
        with open(target_path, 'rb') as fp:
            sig = fp.read(2)
            if sig == 'MZ':
                logger.error('   It looks like this is a Windows binary. If it has an associated PDB file,')
                logger.error('   please run pdbparser.exe to get JSON line information (*.lines) and store')
                logger.error('   that file in the following location: %s.lines', target_path)

        # Print everything we tried if nothing worked
        for err in errors:
            logger.debug(err)

        raise Exception('No usable line information available for %s' % target_path)


class DwarfDebugInfo(DebugInfo):
    def __init__(self, path, search_paths=None, cls=ELFFile):
        super(DwarfDebugInfo, self).__init__(path, search_paths)

        # This tracks the compilation units that have already been parsed
        self._cus = set()
        self._dwarf_info = None
        self._aranges = None
        self._class = cls

    def _parse_function_info(self, cu):
        for die in cu.iter_DIEs():
            if die.tag != 'DW_TAG_subprogram':
                continue

            try:
                lowpc = die.attributes['DW_AT_low_pc'].value
                highpc_attr = die.attributes['DW_AT_high_pc']
                highpc_attr_class = describe_form_class(highpc_attr.form)
                if highpc_attr_class == 'address':
                    highpc = highpc_attr.value
                elif highpc_attr_class == 'constant':
                    highpc = lowpc + highpc_attr.value
                else:
                    logger.warning('invalid DW_AT_high_pc class: %s', highpc_attr_class)
                    continue

                funcname = die.attributes['DW_AT_name'].value
                self._funcs.add(funcname, lowpc, highpc)
            except KeyError:
                continue

    def _parse_cu(self, cu, dwarf_info):
        """
        Retrieves function and line information from a compilation unit.
        This function tries its best to guess the location of source files and normalize
        the stored path information.
        """
        line_program = dwarf_info.line_program_for_CU(cu)
        cu_filepath = cu.get_top_DIE().get_full_path()
        cu_filepath = guess_source_file_path(self._search_paths, cu_filepath)

        # Set the default dir and file path
        src_path = cu_filepath
        src_dir = os.path.dirname(src_path)
        logger.debug('processing %s', src_path)

        self._parse_function_info(cu)
        for entry in line_program.get_entries():
            state = entry.state

            if not state:
                # Special handling for commands that don't set a new state
                if entry.command == dwarf_consts.DW_LNS_set_file:
                    file_entry = line_program['file_entry'][entry.args[0] - 1]
                    if not file_entry.dir_index:
                        # Current directory
                        src_path = guess_source_file_path([src_dir], file_entry.name)

                    elif line_program['include_directory']:
                        include_dir = line_program['include_directory']
                        path = os.path.join(include_dir[file_entry.dir_index - 1], file_entry.name)
                        src_path = guess_source_file_path([src_dir], path)

                elif entry.command == dwarf_consts.DW_LNE_define_file and line_program['include_directory']:
                    include_dir = line_program['include_directory']
                    path = os.path.join(src_dir, include_dir[entry.args[0].dir_index])
                    src_path = guess_source_file_path([src_dir], path)

            elif not state.end_sequence:
                self.add(src_path, state.line, state.address)

    def _parse_info(self, dwarf_info):
        for cu in dwarf_info.iter_CUs():
            if cu.cu_offset in self._cus:
                continue

            self._parse_cu(cu, dwarf_info)
            self._cus.add(cu.cu_offset)

    # pylint: disable=protected-access
    # (accessing useful internal pyelftools methods)
    def _locate_debug_info(self, path):
        with open(path, 'rb') as f:
            binary = self._class(f)

            if not binary.has_dwarf_info():
                raise Exception('Could not find DWARF debug info in %s' % path)

            dwarf_info = binary.get_dwarf_info()
            aranges = dwarf_info.get_aranges()

            if not aranges or not aranges._get_entries():
                raise Exception('DWARF aranges section is missing or empty in %s' % path)

            self._dwarf_info = dwarf_info
            self._aranges = aranges

    def parse_all_info(self):
        """
        This forces loading information about all lines.
        It may be very slow for large files.
        """
        self._parse_info(self._dwarf_info)

    def parse(self):
        """
        DWARF files may have their debug info in a separate file, so this function first checks
        if there is debug info in the target file, and if not, tries to use the debug link.
        """
        try:
            logger.debug('Attempting to look for DWARF info in %s using %s', self.path, str(self._class))
            self._locate_debug_info(self.path)
            return
        except Exception as e:
            logger.debug(e, exc_info=1)

        try:
            # No debug info found, try to use the debug link
            logger.debug('Attempting to find DWARF debug link for %s', self.path)
            debug_file = get_debug_file_for_binary(self.path)
            target_path = guess_target_path(self._search_paths, debug_file)
            self._locate_debug_info(target_path)
            return
        except Exception as e:
            logger.debug(e, exc_info=1)

        raise Exception('Could not find DWARF debug symbols for %s' % self.path)

    # pylint: disable=protected-access
    # (accessing useful internal pyelftools methods)
    def get(self, addr):
        """
        DWARF files may be really big and prefetching all the debug info at once may take minutes.
        Instead, this class overrides the get method in order to fetch compilation units on-demand.
        For this, it uses the aranges section of the binary which allows efficiently translating
        an address to the source file.
        """
        cu_offset = self._aranges.cu_offset_at_addr(addr)
        if cu_offset in self._cus:
            # We already parsed that CU, return closed address available
            return DebugInfo.get(self, addr)

        self._cus.add(cu_offset)
        cu = self._dwarf_info._parse_CU_at_offset(cu_offset)
        self._parse_cu(cu, self._dwarf_info)
        return DebugInfo.get(self, addr)


class Addrs2LinesDebugInfo(DebugInfo):
    def __init__(self, path, search_paths=None, s2e_prefix=''):
        super(Addrs2LinesDebugInfo, self).__init__(path, search_paths)
        self._s2e_prefix = s2e_prefix

    def parse(self):
        candidates = [self.path, os.path.realpath(self.path)]

        parsed = False
        for path in candidates:
            try:
                stdout_data = _invoke_addrs2_lines(self._s2e_prefix, path, '', False, False)
            except Exception:
                continue

            lines = json.loads(stdout_data)

            for source_file, data in list(lines.items()):
                file_path = guess_source_file_path(self._search_paths, source_file)
                for line in data.get('lines', []):
                    for address in line[1]:
                        self.add(file_path, line[0], address)
                        parsed = True

            if parsed:
                break

        if not parsed:
            raise Exception('Could not get debug info from {self.path} using addrs2lines')


class JsonDebugInfo(DebugInfo):
    """
    The line information must have the following format:

    {
        "path/to/file1": [
           [line, [addresses]], [line, [addresses]], ...
        ],
        "path/to/file2": [
           ...
        ]
    }

    This is typically used to get coverage for Windows binaries.
    The pdbparser.exe tool takes a PDB and EXE file, and outputs
    data in the above format.
    """
    def _parse_info(self, lines):
        for filepath, line_info in lines.items():
            filepath = guess_source_file_path(self._search_paths, filepath)
            for line in line_info:
                line_number = line[0]
                addresses = line[1]
                for address in addresses:
                    self.add(filepath, line_number, address)

    def parse(self):
        candidates = [
            '%s.lines' % self.path,
            '%s.lines' % os.path.realpath(self.path)
        ]

        for path in candidates:
            if not os.path.exists(path):
                continue

            logger.debug('Attempting to parse JSON debug data from %s', path)
            with open(path, 'r') as f:
                lines = json.loads(f.read())
                self._parse_info(lines)
                return

        raise Exception(f'Could not find any of {candidates}')


def _invoke_addrs2_lines(s2e_prefix, target_path, json_in, include_covered_files_only, get_coverage):
    addrs2lines = os.path.join(s2e_prefix, 'bin', 'addrs2lines')
    if not os.path.exists(addrs2lines):
        logger.warning('%s does not exist. Make sure you have updated and rebuilt S2E.', addrs2lines)
        raise OSError(errno.ENOENT, os.strerror(errno.ENOENT), addrs2lines)

    args = [addrs2lines]

    if get_coverage:
        args += ['-coverage', '-pretty']
        if include_covered_files_only:
            args.append('-include-covered-files-only')

    args.append(target_path)

    p = Popen(args, stdout=PIPE, stdin=PIPE)

    stdout_data = p.communicate(input=json_in.encode())[0]
    if p.returncode:
        raise Exception('addrs2lines failed with error code %d' % p.returncode)

    return stdout_data


def _get_coverage_fast(s2e_prefix, search_paths, target, addr_counts, include_covered_files_only):
    """
    This functions uses addrs2lines to compute code coverage.
    It is much faster than using pyelftools. It takes a few seconds to get coverage for the Linux kernel,
    vs a few (tens) of minutes with pyelftools.
    """
    address_ranges = []
    for addr, _ in list(addr_counts.items()):
        address_ranges.append((addr, 1))

    stdout_data = _invoke_addrs2_lines(
        s2e_prefix,
        guess_target_path(search_paths, target),
        json.dumps(address_ranges),
        include_covered_files_only, True
    )

    lines = json.loads(stdout_data)

    ret = {}
    for source_file, data in list(lines.items()):
        line_counts = {}
        for line in data.get('lines', []):
            line_counts[line[0]] = line[1]
        ret[source_file] = line_counts

    return ret


class SymbolManager:
    """
    This class manages debug information for binary files.
    It implements addr2line equivalent and provides methods to compute code coverage.
    """
    def __init__(self, s2e_prefix, search_paths=None):
        """
        Initialize an instance of the symbol manager.
        :param search_paths: list of paths where to search for binaries when they are
        not specified with an absolute path.
        """
        if search_paths is None:
            search_paths = []

        self._targets = {}
        self._search_paths = search_paths
        self._s2e_prefix = s2e_prefix

    def _get_syms(self, target):
        syms = None

        logger.debug('Fetching target %s', target)
        if target in self._targets:
            return self._targets[target]

        try:
            actual_target = guess_target_path(self._search_paths, target)
            syms = DebugInfo.from_file(self._s2e_prefix, self._search_paths, actual_target)
            self._targets[target] = syms
        except Exception as e:
            logger.debug(e, exc_info=1)
            self._targets[target] = None

        return syms

    def get_target(self, target):
        syms = self._get_syms(target)
        if not syms:
            raise Exception('Could not find symbols for %s' % target)

        return syms

    def get(self, target, addr):
        return self.get_target(target).get(addr)

    def get_coverage(self, target, addr_counts, include_covered_files_only=False):
        """
        Map addresses to line numbers in the source code file.

        Args:
            target: the name of the executable file for which to get coverage

            addr_counts: A dictionary mapping instruction addresses executed by S2E
                         (and recorded by the ``TranslationBlockCoverage`` plugin)
                         to the number of times they were executed.

            include_covered_files_only:
                when true, does not include any files that have not been covered
                in addr_counts. This is useful for very large binaries where only
                a small fraction of files are covered.

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

        try:
            return _get_coverage_fast(self._s2e_prefix, self._search_paths, target, addr_counts,
                                      include_covered_files_only)
        except Exception as e:
            logger.warning('addrs2lines failed (%s), trying to get coverage using pyelftools (may be slow!)', e)
            return self.get_target(target).get_coverage(addr_counts, include_covered_files_only)

"""
Copyright (c) 2018 Cyberhaven
Based on pyelftools ELFFile, written by Eli Bendersky (eliben@gmail.com)

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

import ctypes
import pefile

from elftools.common.py3compat import BytesIO
from elftools.dwarf.dwarfinfo import DebugSectionDescriptor
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationHandler


class PEFile(object):
    """
    This class exposes DWARF debug info in a PE file in a way that is compatible with pyelftools.
    """

    # This is the size of a COFF symbol table entry
    SYMENT_SIZE = 8 + 4 + 2 + 2 + 1 + 1

    # Lift some methods from ELFFile to avoid code duplication
    get_dwarf_info = ELFFile.__dict__['get_dwarf_info']
    has_dwarf_info = ELFFile.__dict__['has_dwarf_info']

    def __init__(self, stream):
        self._data = stream.read()
        self._pe = pefile.PE(data=self._data)
        self._section_name_map = None
        self._patch_section_names()

        # For compatibility with ELFFile
        self.little_endian = True
        self.elfclass = self.pointer_size() * 8

    def _patch_section_names(self):
        """
        Vanilla pefile module does not understand section names encoded in the COFF string table,
        so we patch every section name here.
        """
        for sec in self._pe.sections:
            self._expand_section_name(sec)

    def num_sections(self):
        """
        Number of sections in the file
        """
        return len(self._pe.sections)

    def get_section(self, n):
        """
        Get the section at index #n from the file (Section object or a subclass)
        """
        return self._pe.sections[n]

    def get_section_by_name(self, name):
        """
        Get a section from the file, by name. Return None if no such section exists.
        """
        # The first time this method is called, construct a name to numbermapping
        if self._section_name_map is None:
            self._section_name_map = {}
            for i, sec in enumerate(self.iter_sections()):
                self._expand_section_name(sec)
                self._section_name_map[sec.Name] = i
        secnum = self._section_name_map.get(name, None)
        return None if secnum is None else self.get_section(secnum)

    def iter_sections(self):
        """
        Yield all the sections in the file
        """
        for i in range(self.num_sections()):
            yield self.get_section(i)

    def get_machine_arch(self):
        """
        Return the machine architecture, as detected from the ELF header.
        Not all architectures are supported at the moment.
        """
        if self._pe.FILE_HEADER.Machine == pefile.MACHINE_TYPE['IMAGE_FILE_MACHINE_AMD64']:
            return 'x64'
        if self._pe.FILE_HEADER.Machine == pefile.MACHINE_TYPE['IMAGE_FILE_MACHINE_I386']:
            return 'x86'
        return '<unknown>'

    def pointer_size(self):
        if self._pe.FILE_HEADER.Machine == pefile.MACHINE_TYPE['IMAGE_FILE_MACHINE_I386']:
            return 4
        if self._pe.FILE_HEADER.Machine == pefile.MACHINE_TYPE['IMAGE_FILE_MACHINE_AMD64']:
            return 8
        raise Exception('Unsupported machine type %#x' % self._pe.FILE_HEADER.Machine)

    def _read_dwarf_section(self, section, relocate_dwarf_sections):
        """
        Read the contents of a DWARF section from the stream and return a
        DebugSectionDescriptor. Apply relocations if asked to.
        """
        # The section data is read into a new stream, for processing
        section_stream = BytesIO()
        section_stream.write(section.get_data())

        if relocate_dwarf_sections:
            reloc_handler = RelocationHandler(self)
            reloc_section = reloc_handler.find_relocations_for_section(section)
            if reloc_section is not None:
                reloc_handler.apply_section_relocations(section_stream, reloc_section)

        return DebugSectionDescriptor(
            stream=section_stream,
            name=section.name,
            global_offset=section.PointerToRawData,
            size=section.SizeOfRawData,
            address=section.get_rva_from_offset(0))

    def _expand_section_name(self, sec):
        """
        Section names that are longer than 8 characters are instead named "/nn", where nn is a decimal-coded
        offset into the COFF string table. We must handle this encoding because that's how DWARF section names
        are encoded.
        """
        if sec.Name[0] != '/':
            return

        offset = int(sec.Name[1:].strip('\0'))
        sym_table = self._pe.FILE_HEADER.PointerToSymbolTable
        sym_count = self._pe.FILE_HEADER.NumberOfSymbols

        if not sym_count or not sym_table:
            # No COFF info present
            return

        sym_table_size = sym_count * PEFile.SYMENT_SIZE
        str_table_offset = sym_table + sym_table_size + offset

        # The string table holds null-terminated strings
        name = ctypes.create_string_buffer(self._data[str_table_offset:]).value
        sec.Name = name

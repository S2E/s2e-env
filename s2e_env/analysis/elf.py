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


from elftools.elf.dynamic import DynamicSegment
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection

from s2e_env import CONSTANTS


class ELFAnalysis:
    """
    Support class for doing some simple static analysis on ELF files.
    """

    def __init__(self, elf_path):
        self._elf_path = elf_path
        self._elf_file = None
        self._elf = None

    def __enter__(self):
        self._elf_file = open(self._elf_path, 'rb')
        self._elf = ELFFile(self._elf_file)

        return self

    def __exit__(self, exec_type, exec_value, traceback):
        if self._elf_file:
            self._elf_file.close()

        return False

    def is_dynamically_linked(self):
        """
        Determine if a ELF file is dynamically linked.

        Determine this by checking if a dynamic segment exists.

        Args:
            elf_path: Path to the ELF file.

        Returns:
            ``True`` if the ELF file is dynamically linked, or ``False``
            otherwise.
        """
        for segment in self._elf.iter_segments():
            if isinstance(segment, DynamicSegment):
                return True

        return False

    def get_modelled_functions(self):
        """
        Get a list of imported functions that we can replace with a model from
        S2E's ``FunctionModels`` plugin.

        Args:
            elf_path: Path to the ELF file.

        Returns:
            A list of functions imported that we can replace with models from
            S2E's ``FunctionModels`` plugin.
        """
        def is_modelled_func(symbol):
            return (symbol['st_info']['bind'] == 'STB_GLOBAL' and
                    symbol['st_info']['type'] == 'STT_FUNC' and
                    symbol.name in CONSTANTS['function_models'])

        # Find the symbol table(s)
        modelled_functions = set()
        for section in self._elf.iter_sections():
            if isinstance(section, SymbolTableSection):
                # Look for a function that is supported by the FunctionModels
                # plugin
                for symbol in section.iter_symbols():
                    if is_modelled_func(symbol):
                        modelled_functions.add(symbol.name)

        # Must return a list so we can serialize it to JSON
        return list(modelled_functions)

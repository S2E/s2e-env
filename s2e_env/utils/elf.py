from elftools.elf.dynamic import DynamicSegment
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection

from s2e_env import CONSTANTS


class ELFAnalysis(object):
    """
    Support class for doing some simple static analysis on ELF files.
    """

    def __init__(self, elf_path):
        self._elf_path = elf_path
        self._elf_file = None
        self._elf = None

    def __enter__(self):
        self._elf_file = open(self._elf_path, 'r')
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

        # Find the symbol table
        for section in self._elf.iter_sections():
            if isinstance(section, SymbolTableSection):
                # Look for a function that is supported by the FunctionModels
                # plugin
                modelled_functions = [symbol.name for symbol in
                                      section.iter_symbols()
                                      if is_modelled_func(symbol)]

        return modelled_functions

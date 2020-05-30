"""
Copyright (c) 2017 Dependable Systems Laboratory, EPFL
Copyright (c) 2018 Adrian Herrera

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


import logging
import os

logger = logging.getLogger('target')


class Target:
    """
    Encapsulates a program (e.g., executable, driver, DLL, etc.) to be analyzed
    by S2E.
    """

    @staticmethod
    def empty():
        """Create an empty target."""
        return Target(None, None, None, None)

    # pylint: disable=too-many-arguments
    def __init__(self, path, args, arch, _os, aux_files=None):
        self._path = path
        self._arch = arch
        self._os = _os
        self._args = args if args else []

        if not aux_files:
            aux_files = []

        self._aux_files = aux_files

    @property
    def path(self):
        """The path of the program under analysis."""
        return self._path

    @property
    def raw_args(self):
        """The program arguments."""
        return self._args

    @property
    def args(self):
        """The processed program arguments."""

        # The target arguments are specified using a format similar to the
        # American Fuzzy Lop fuzzer. Options are specified as normal, however
        # for programs that take input from a file, '@@' is used to mark the
        # location in the target's command line where the input file should be
        # placed. This will automatically be substituted with a symbolic file
        # in the S2E bootstrap script.
        parsed_args = ['"${SYMB_FILE}"' if arg == '@@' else arg
                       for arg in self._args]

        # Quote arguments that have spaces in them
        parsed_args = [f'"{arg}"' if ' ' in arg else arg
                       for arg in parsed_args]

        return parsed_args

    @args.setter
    def args(self, value):
        self._args = value

    @property
    def name(self):
        """The basename of the target path"""
        return os.path.basename(self.path) if self.path else None

    @property
    def names(self):
        """The basename of the files"""
        ret = []
        for file in self.files:
            ret += [os.path.basename(file)]
        return ret

    @property
    def arch(self):
        """The architecture (e.g., i386, x86-64, etc.) of the program under analysis."""
        return self._arch

    @property
    def operating_system(self):
        """The operating system that the target executes on."""
        return self._os

    @property
    def aux_files(self):
        """A list of any auxiliary files required by S2E to analysis the target program."""
        return self._aux_files

    @property
    def files(self):
        """This contains paths to all the files that must be downloaded into the guest."""
        return ([self.path] if self.path else []) + self.aux_files

    def is_empty(self):
        """Returns ``True`` if the target is an empty one."""
        return not self._path

    def __str__(self):
        return 'Target(path=%s,arch=%s)' % (self._path, self._arch)

    def toJSON(self):
        return {
            'path': self.path,
            'files': self.files,
            'name': self.name,
            'arch': self.arch,
            'os': self.operating_system,
            'aux_files': self.aux_files
        }

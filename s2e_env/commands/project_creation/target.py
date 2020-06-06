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


class TargetArguments:
    def __init__(self, args):
        self._args = args if args else []
        # These are seed files that we'll generate automatically when encountering an '@@' argument
        self._blank_seed_files = []

        # These are actual seed files specified by the user on the target's command line
        self._seed_files = []

        # Maps a basename on the command line to a full path of the corresponding symbolic file
        self._name_to_path = {}
        self._translate_args()

    def _translate_args(self):
        """
        It is possible to pass file paths as command line arguments to a target.
        This function guesses which arguments are file paths and ensures that these files are uploaded into the guest.
        It also patches the argument so that it is valid in the guest.
        """
        new_args = []
        input_idx = 0

        for arg in self._args:
            if arg.startswith('@@'):
                suffix = arg[2:]
                if suffix:
                    name = f'input-{input_idx}-{suffix}'
                else:
                    name = f'input-{input_idx}'
                new_args.append(name)
                self._blank_seed_files.append(name)
                input_idx += 1
            elif os.path.exists(arg):
                self._seed_files.append(arg)
                na = os.path.basename(arg)
                new_args.append(na)
            else:
                new_args.append(arg)
        self._args = new_args

    def generate_symbolic_files(self, root, use_seeds):
        blank_seed_file_paths = []
        for file in self._blank_seed_files:
            path = os.path.join(root, file)
            blank_seed_file_paths.append(path)
            self._name_to_path[file] = path

            if not use_seeds:
                with open(path, 'w') as fp:
                    fp.write('x' * 256)
                with open(path + '.symranges', 'w') as fp:
                    fp.write('# This file specifies offset-size pairs to make symbolic\n')
                    fp.write('0-256')

        self._blank_seed_files = blank_seed_file_paths

        for file in self._seed_files:
            name = os.path.basename(file)
            path = os.path.join(root, name)
            self._name_to_path[name] = file
            with open(path + '.symranges', 'w') as fp:
                fp.write('# This file specifies offset-size pairs to make symbolic\n')
                fp.write('# 0-0')

    @property
    def raw_args(self):
        return self._args

    @property
    def blank_seed_files(self):
        return self._blank_seed_files

    @property
    def symbolic_files(self):
        return self._blank_seed_files + self._seed_files

    @property
    def symbolic_file_names(self):
        ret = []
        for f in self.symbolic_files:
            ret.append(os.path.basename(f))
        return ret

    def get_resolved_args(self, symfile_dir):
        """The processed program arguments."""

        # The target arguments are specified using a format similar to the
        # American Fuzzy Lop fuzzer. Options are specified as normal, however
        # for programs that take input from a file, '@@' is used to mark the
        # location in the target's command line where the input file should be
        # placed. This will automatically be substituted with a symbolic file
        # in the S2E bootstrap script.
        parsed_args = []
        for arg in self._args:
            if arg in self._name_to_path:
                parsed_args.append(f'{symfile_dir}{arg}')
            else:
                parsed_args.append(arg)

        # Quote arguments that have spaces or backslashes in them
        parsed_args = [f"'{arg}'" if ' ' in arg or '\\' in arg else arg for arg in parsed_args]

        return parsed_args


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
        self._args = TargetArguments(args)
        self._translated_path = None

        if not aux_files:
            aux_files = []

        self._aux_files = aux_files

    @property
    def path(self):
        """The path of the program under analysis."""
        return self._path

    @property
    def translated_path(self):
        r"""
        If the target executable is already present in the base image, this returns
        the path inside the image. E.g., if a user specify the following binary:
        ./images/windows-xpsp3pro-i386/office2010/guestfs/program files/microsoft office/office14/winword.exe
        the translated path will be c:\program files\microsoft office\office14\winword.exe.
        """
        return self._translated_path

    @translated_path.setter
    def translated_path(self, value):
        self._translated_path = value

    @property
    def args(self):
        """The program arguments."""
        return self._args

    @args.setter
    def args(self, value):
        self._args = TargetArguments(value)

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
        return ([self.path] if self.path and not self.translated_path else []) + self.aux_files

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

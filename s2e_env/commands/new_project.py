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


import argparse
import os
import re

from magic import Magic

from s2e_env.command import EnvCommand, CommandError
from s2e_env.manage import call_command
from s2e_env.commands.project_creation import Project
from s2e_env.commands.project_creation.config import \
    CGCProjectConfiguration, LinuxProjectConfiguration, WindowsProjectConfiguration, WindowsDLLProjectConfiguration

# Paths
FILE_DIR = os.path.dirname(__file__)
CGC_MAGIC = os.path.join(FILE_DIR, '..', 'dat', 'cgc.magic')

# Magic regexs
CGC_REGEX = re.compile(r'^CGC 32-bit')
ELF32_REGEX = re.compile(r'^ELF 32-bit')
ELF64_REGEX = re.compile(r'^ELF 64-bit')
PE32_REGEX = re.compile(r'^PE32 executable')
PE64_REGEX = re.compile(r'^PE32\+ executable')
MSDOS_REGEX = re.compile(r'^MS-DOS executable')
DLL32_REGEX = re.compile(r'^PE32 executable \(DLL\)')
DLL64_REGEX = re.compile(r'^PE32\+ executable \(DLL\)')


def _parse_sym_args(sym_args_str):
    """
    Parses a list of argument indices to make symbolic.

    ``sym_args_str`` should be a string of space-separated integers that
    correspond to a program argument to make symbolic. E.g. to make the first
    argument symbolic, ``sym_args_str`` should be "1". To make the first and
    third arguments symbolic, ``sym_args_str`` should be "1 3".
    """
    sym_args = []

    if not sym_args_str:
        return sym_args

    for i in sym_args_str.split(' '):
        try:
            sym_args.append(int(i))
        except ValueError:
            raise argparse.ArgumentTypeError('\'%s\' is not a valid index' % i)

    return sym_args


class Command(EnvCommand):
    """
    Initialize a new analysis project.
    """

    help = 'Initialize a new analysis project.'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('target', nargs=1,
                            help='Path to the target file to analyze')
        parser.add_argument('target_args', nargs=argparse.REMAINDER,
                            help='Arguments to the target program. Use @@ '
                                 'as an input file marker that is automatically '
                                 'substituted by a file with symbolic content')
        parser.add_argument('-n', '--name', required=False, default=None,
                            help='The name of the project. Defaults to the '
                                 'name of the target program.')
        parser.add_argument('-i', '--image', required=False, default=None,
                            help='The name of an image in the ``images`` '
                                 'directory. If missing, the image will be '
                                 'guessed based on the type of the binary')
        parser.add_argument('-d', '--download-image', required=False,
                            action='store_true',
                            help='Download a suitable image if it is not available')
        parser.add_argument('-s', '--use-seeds', action='store_true',
                            help='Use this option to use seeds for creating '
                                 'concolic files. The user must create these '
                                 'seeds themselves and place them in the '
                                 'project\'s ``seeds`` directory')
        parser.add_argument('-a', '--sym-args', type=_parse_sym_args, default='',
                            help='A space-separated list of target argument '
                                 'indices to make symbolic')
        parser.add_argument('-f', '--force', action='store_true',
                            help='If a project with the given name already '
                                 'exists, replace it')

    def handle(self, *args, **options):
        # Need an absolute path for the target in order to simplify
        # symlink creation.
        target_path = options['target'][0]
        target_path = os.path.realpath(target_path)

        # Check that the target actually exists
        if not os.path.isfile(target_path):
            raise CommandError('Target %s does not exist' % target_path)

        default_magic = Magic()
        magic_checks = [
            (Magic(magic_file=CGC_MAGIC), CGC_REGEX, CGCProjectConfiguration, 'i386'),
            (default_magic, ELF32_REGEX, LinuxProjectConfiguration, 'i386'),
            (default_magic, ELF64_REGEX, LinuxProjectConfiguration, 'x86_64'),
            (default_magic, DLL32_REGEX, WindowsDLLProjectConfiguration, 'i386'),
            (default_magic, DLL64_REGEX, WindowsDLLProjectConfiguration, 'x86_64'),
            (default_magic, PE32_REGEX, WindowsProjectConfiguration, 'i386'),
            (default_magic, PE64_REGEX, WindowsProjectConfiguration, 'x86_64'),
            (default_magic, MSDOS_REGEX, WindowsProjectConfiguration, 'i386')
        ]

        # Check the target program against the valid file types
        for magic_check, regex, proj_config_class, arch in magic_checks:
            magic = magic_check.from_file(target_path)
            matches = regex.match(magic)

            # If we find a match, create that project. The user instructions
            # are returned
            if matches:
                options['target'] = target_path
                options['target_arch'] = arch

                return call_command(Project(proj_config_class), **options)

        # Otherwise no valid file type was found
        raise CommandError('%s is not a valid target for S2E analysis' %
                           target_path)

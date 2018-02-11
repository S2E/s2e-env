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
import logging
import os
import re

from magic import Magic

from s2e_env.infparser.driver import Driver
from s2e_env.command import EnvCommand, CommandError
from s2e_env.manage import call_command
from s2e_env.commands.project_creation import Project
from s2e_env.commands.project_creation.config import \
    CGCProjectConfiguration, LinuxProjectConfiguration, WindowsProjectConfiguration, WindowsDLLProjectConfiguration, \
    WindowsDriverProjectConfiguration

logger = logging.getLogger('new_project')

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


def get_arch(target_path):
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
            return arch, proj_config_class

    return None, None


def _handle_inf(target_path, **options):
    logger.info('Detected Windows INF file, attempting to create device driver project...')
    driver = Driver(target_path)
    driver.analyze()
    driver_files = driver.get_files()
    if not driver_files:
        raise CommandError('Driver has no files')

    base_dir = os.path.dirname(target_path)

    logger.info('  Driver files:')
    file_paths = []
    first_sys_file = None
    for f in driver_files:
        full_path = os.path.join(base_dir, f)
        if not os.path.exists(full_path):
            if full_path.endswith('.cat'):
                logger.warn('Catalog file %s is missing', full_path)
                continue
            else:
                raise CommandError('%s does not exist' % full_path)

        logger.info('    %s', full_path)
        file_paths.append(full_path)

        if full_path.endswith('.sys'):
            first_sys_file = full_path

    # Pick the architecture of the first sys file
    # TODO: prompt the user to select the right driver
    if not first_sys_file:
        raise CommandError('Could not find any *.sys file')

    arch, _ = get_arch(first_sys_file)
    if arch is None:
        raise CommandError('Could not determine architecture for %s' % first_sys_file)

    options['target'] = target_path
    options['target_arch'] = arch

    # All the files to download into the guest.
    options['target_files'] = [target_path] + file_paths

    # TODO: support multiple kernel drivers
    options['modules'] = [(os.path.basename(first_sys_file), True)]
    options['processes'] = []

    call_command(Project(WindowsDriverProjectConfiguration), **options)

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

        arch, proj_config_class = get_arch(target_path)
        if arch:
            options['target'] = target_path
            options['target_files'] = [target_path]
            options['target_arch'] = arch

            # The module list is a list of tuples where the first element is
            # the module name and the second element is True if the module is
            # a kernel module
            options['modules'] = [(os.path.basename(target_path), False)]

            options['processes'] = []
            if not isinstance(proj_config_class, WindowsDLLProjectConfiguration):
                options['processes'].append(os.path.basename(target_path))

            call_command(Project(proj_config_class), **options)
        elif target_path.endswith('.inf'):
            _handle_inf(target_path, **options)
        else:
            raise CommandError('%s is not a valid target for S2E analysis' %
                               target_path)

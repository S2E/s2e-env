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

from s2e_env.command import EnvCommand, CommandError
from s2e_env.commands.project_creation.abstract_project import AbstractProject
from s2e_env.commands.project_creation.cgc_project import CGCProject
from s2e_env.commands.project_creation.linux_project import LinuxProject
from s2e_env.commands.project_creation.windows_project import WindowsProject, WindowsDLLProject, WindowsDriverProject
from s2e_env.infparser.driver import Driver
from s2e_env.manage import call_command


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

PROJECT_CLASSES = {
    'cgc': CGCProject,
    'linux': LinuxProject,
    'windows': WindowsProject,
}


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


def _get_arch(target_path):
    """
    Check that the given target is supported by S2E.

    The target's magic is checked to see if it is a supported file type (e.g.
    ELF, PE, etc.). The architecture that the target was compiled for (e.g.
    i386, x64, etc.) is also checked.

    Returns:
        A tuple containing the target's architecture and a project class is
        returned.
    """
    default_magic = Magic()
    magic_checks = [
        (Magic(magic_file=CGC_MAGIC), CGC_REGEX, CGCProject, 'i386'),
        (default_magic, ELF32_REGEX, LinuxProject, 'i386'),
        (default_magic, ELF64_REGEX, LinuxProject, 'x86_64'),
        (default_magic, DLL32_REGEX, WindowsDLLProject, 'i386'),
        (default_magic, DLL64_REGEX, WindowsDLLProject, 'x86_64'),
        (default_magic, PE32_REGEX, WindowsProject, 'i386'),
        (default_magic, PE64_REGEX, WindowsProject, 'x86_64'),
        (default_magic, MSDOS_REGEX, WindowsProject, 'i386')
    ]

    # Check the target program against the valid file types
    for magic_check, regex, proj_class, arch in magic_checks:
        magic = magic_check.from_file(target_path)
        matches = regex.match(magic)

        # If we find a match, create that project
        if matches:
            return arch, proj_class

    return None, None


def _handle_win_driver_project(target_path, driver_files, *args, **options):
    first_sys_file = None
    for f in driver_files:
        if f.endswith('.sys'):
            first_sys_file = f

    # TODO: prompt the user to select the right driver
    if not first_sys_file:
        raise CommandError('Could not find any *.sys file in the INF file. '
                           'Make sure the INF file is valid and belongs to a '
                           'Windows driver')

    # Determine the architecture of the first sys file
    first_sys_file = os.path.realpath(first_sys_file)
    arch, _ = _get_arch(first_sys_file)
    if not arch:
        raise CommandError('Could not determine architecture for %s' %
                           first_sys_file)

    options['target_files'] = [target_path] + driver_files
    options['target_arch'] = arch

    # TODO: support multiple kernel drivers
    options['modules'] = [(os.path.basename(first_sys_file), True)]

    call_command(WindowsDriverProject(), *args, **options)


def _extract_inf_files(target_path):
    driver = Driver(target_path)
    driver.analyze()
    driver_files = driver.get_files()
    if not driver_files:
        raise CommandError('Driver has no files')

    base_dir = os.path.dirname(target_path)

    logger.info('  Driver files:')
    file_paths = []
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

    return list(set(file_paths))


def _handle_generic_project(target_path, *args, **options):
    arch, proj_class = _get_arch(target_path)
    if not arch:
        raise CommandError('%s is not a valid target for S2E analysis' % target_path)

    options['target_files'] = [target_path]
    options['target_arch'] = arch

    # The module list is a list of tuples where the first element is the module
    # name and the second element is True if the module is a kernel module
    options['modules'] = [(os.path.basename(target_path), False)]

    call_command(proj_class(), *args, **options)


def _handle_with_file(target_path, *args, **options):
    # Check that the target is a valid file
    if not os.path.isfile(target_path):
        raise CommandError('Target %s is not valid' % target_path)

    if target_path.endswith('.inf'):
        # Don't call realpath on an inf file. Doing so will force
        # lookup of binary files in the same directory as the actual inf file.
        logger.info('Detected Windows INF file, attempting to create a driver project...')
        driver_files = _extract_inf_files(target_path)

        _handle_win_driver_project(target_path, driver_files, *args, **options)
    elif target_path.endswith('.sys'):
        logger.info('Detected Windows SYS file, attempting to create a driver project...')
        target_path = os.path.realpath(target_path)

        _handle_win_driver_project(target_path, [], *args, **options)
    else:
        target_path = os.path.realpath(target_path)

        _handle_generic_project(target_path, *args, **options)


def _handle_empty_project(*args, **options):
    if not options['no_target']:
        raise CommandError('No target binary specified. Use the -m option to '
                           'create an empty project')

    if not options['image']:
        raise CommandError('An empty project requires a VM image. Use the -i '
                           'option to specify the image')

    if not options['name']:
        raise CommandError('An empty project requires a name. Use the -n '
                           'option to specify one')

    project_types = PROJECT_CLASSES.keys()
    if options['type'] not in project_types:
        raise CommandError('An empty project requires a type. Use the -t '
                           'option and specify one from %s' % project_types)

    options['target_files'] = []
    options['target_arch'] = None

    # The module list is a list of tuples where the first element is
    # the module name and the second element is True if the module is
    # a kernel module
    options['modules'] = []

    project = PROJECT_CLASSES[options['type']]
    call_command(project(), *args, **options)


class Command(EnvCommand):
    """
    Initialize a new analysis project.
    """

    help = 'Initialize a new analysis project.'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('target', nargs='?',
                            help='Path to the target file to analyze')

        parser.add_argument('target_args', nargs=argparse.REMAINDER,
                            help='Arguments to the target program. Use @@ '
                                 'as an input file marker that is automatically '
                                 'substituted by a file with symbolic content')

        parser.add_argument('-n', '--name', required=False, default=None,
                            help='The name of the project. Defaults to the '
                                 'name of the target program')

        parser.add_argument('-i', '--image', required=False, default=None,
                            help='The name of an image in the ``images`` '
                                 'directory. If missing, the image will be '
                                 'guessed based on the type of the binary')

        parser.add_argument('-d', '--download-image', required=False,
                            action='store_true',
                            help='Download a suitable image if it is not available')

        parser.add_argument('-m', '--no-target', required=False, default=False,
                            action='store_true',
                            help='Create an empty, target-less project. Used when no binary is needed')

        parser.add_argument('-t', '--type', required=False, default=None,
                            help='Project type (%s), valid only when creating empty projects' %
                            ','.join(PROJECT_CLASSES.keys()))

        parser.add_argument('-s', '--use-seeds', action='store_true',
                            help='Use this option to use seeds for creating '
                                 'concolic files. The user must create these '
                                 'seeds themselves and place them in the '
                                 'project\'s ``seeds`` directory')

        parser.add_argument('--enable-pov-generation', action='store_true',
                            help='Enables PoV generation')

        parser.add_argument('-a', '--sym-args', type=_parse_sym_args, default='',
                            help='A space-separated list of target argument '
                                 'indices to make symbolic')

        parser.add_argument('-f', '--force', action='store_true',
                            help='If a project with the given name already '
                                 'exists, replace it')

    def handle(self, *args, **options):
        # The 'project_class' option is not exposed as a command-line argument:
        # it is typically used when creating a custom project programatically.
        # It provides a class that is instantiated with the current
        # command-line arguments and options
        proj_class = options.get('project_class')
        if proj_class:
            if not issubclass(proj_class, AbstractProject):
                raise CommandError('Custom projects must be a subclass of '
                                   'AbstractProject')
            call_command(proj_class(), *args, **options)
        elif options['target']:
            _handle_with_file(options.pop('target'), *args, **options)
        else:
            _handle_empty_project(*args, **options)

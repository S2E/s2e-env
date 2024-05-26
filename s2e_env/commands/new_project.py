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
from s2e_env.commands.project_creation import CGCProject, LinuxProject, AbstractProject
from s2e_env.commands.project_creation import WindowsExeProject, \
        WindowsDLLProject, WindowsDriverProject, BIOSProject
from s2e_env.commands.project_creation import Target
from s2e_env.commands.project_creation.abstract_project import validate_arguments, SUPPORTED_TOOLS
from s2e_env.infparser.driver import Driver
from s2e_env.manage import call_command


logger = logging.getLogger('new_project')

PROJECT_TYPES = {
    'cgc': CGCProject,
    'linux': LinuxProject,
    'windows': WindowsExeProject,
    'windows_dll': WindowsDLLProject,
    'windows_driver': WindowsDriverProject,
    'bios': BIOSProject
}

# Paths
FILE_DIR = os.path.dirname(__file__)
CGC_MAGIC = os.path.join(FILE_DIR, '..', 'dat', 'cgc.magic')

# Magic regexs
CGC_REGEX = re.compile(r'^CGC 32-bit')
ELF32_REGEX = re.compile(r'^ELF 32-bit')
ELF64_REGEX = re.compile(r'^ELF 64-bit')
DLL32_REGEX = re.compile(r'^PE32 executable \(DLL\)')
DLL64_REGEX = re.compile(r'^PE32\+ executable \(DLL\)')
WIN32_DRIVER_REGEX = re.compile(r'^PE32 executable \(native\)')
WIN64_DRIVER_REGEX = re.compile(r'^PE32\+ executable \(native\)')
PE32_REGEX = re.compile(r'^PE32 executable')
PE64_REGEX = re.compile(r'^PE32\+ executable')
MSDOS_REGEX = re.compile(r'^MS-DOS executable')

ARCH_I386 = 'i386'
ARCH_X86_64 = 'x86_64'
SUPPORTED_ARCHS=[ARCH_I386, ARCH_X86_64]

def _determine_arch_and_proj(target_path):
    """
    Check that the given target is supported by S2E.

    The target's magic is checked to see if it is a supported file type (e.g.
    ELF, PE, etc.). The architecture and operating system that the target was
    compiled for (e.g., i386 Windows, x64 Linux, etc.) is also checked.

    Returns:
        A tuple containing the target's architecture, operating system and a
        project class. A tuple containing three ``None``s is returned on
        failure.
    """
    default_magic = Magic()
    magic_checks = (
        (Magic(magic_file=CGC_MAGIC), CGC_REGEX, CGCProject, ARCH_I386, 'decree'),
        (default_magic, ELF32_REGEX, LinuxProject, ARCH_I386, 'linux'),
        (default_magic, ELF64_REGEX, LinuxProject, ARCH_X86_64, 'linux'),
        (default_magic, DLL32_REGEX, WindowsDLLProject, ARCH_I386, 'windows'),
        (default_magic, DLL64_REGEX, WindowsDLLProject, ARCH_X86_64, 'windows'),
        (default_magic, WIN32_DRIVER_REGEX, WindowsDriverProject, ARCH_I386, 'windows'),
        (default_magic, WIN64_DRIVER_REGEX, WindowsDriverProject, ARCH_X86_64, 'windows'),
        (default_magic, PE32_REGEX, WindowsExeProject, ARCH_I386, 'windows'),
        (default_magic, PE64_REGEX, WindowsExeProject, ARCH_X86_64, 'windows'),
        (default_magic, MSDOS_REGEX, WindowsExeProject, ARCH_I386, 'windows'),
    )

    # Need to resolve symbolic links, otherwise magic will report the file type
    # as being a symbolic link
    target_path = os.path.realpath(target_path)

    # Check the target program against the valid file types
    for magic_check, regex, proj_class, arch, operating_sys in magic_checks:
        magic = magic_check.from_file(target_path)

        # If we find a match, create that project
        if regex.match(magic):
            return arch, operating_sys, proj_class

    return None, None, None


def _extract_inf_files(target_path):
    """Extract Windows driver files from an INF file."""
    driver = Driver(target_path)
    driver.analyze()
    driver_files = driver.get_files()
    if not driver_files:
        raise Exception('Driver has no files')

    base_dir = os.path.dirname(target_path)

    logger.info('  Driver files:')
    file_paths = []
    for f in driver_files:
        full_path = os.path.join(base_dir, f)
        if not os.path.exists(full_path):
            if full_path.endswith('.cat'):
                logger.warning('Catalog file %s is missing', full_path)
                continue
            raise Exception(f'{full_path} does not exist')

        logger.info('    %s', full_path)
        file_paths.append(full_path)

    return list(set(file_paths))


def _translate_target_to_files(path):
    """
    :param path: The path to the target
    :return: The list of files associated with the target. The first
    item in the list is the main target name.
    """

    if not os.path.isfile(path):
        raise Exception(f'Target {path} does not exist')

    if path.endswith('.inf'):
        logger.info('Detected Windows INF file, attempting to create a driver project...')
        driver_files = _extract_inf_files(path)

        first_sys_file = None
        for f in driver_files:
            if f.endswith('.sys'):
                first_sys_file = f

        # TODO: prompt the user to select the right driver
        if not first_sys_file:
            raise Exception('Could not find a *.sys file in the INF '
                            'file. Make sure that the INF file is valid '
                            'and belongs to a Windows driver')

        path_to_analyze = first_sys_file
        aux_files = driver_files
    else:
        path_to_analyze = path
        aux_files = []

    return [path_to_analyze] + aux_files


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
        except ValueError as e:
            raise argparse.ArgumentTypeError(f'\'{i}\' is not a valid index') from e

    return sym_args


def target_from_file(path, args=None, project_class=None, custom_arch=None):
    files = _translate_target_to_files(path)
    path_to_analyze = files[0]
    aux_files = files[1:]

    arch, op_sys, proj_class = _determine_arch_and_proj(path_to_analyze)
    if not arch:
        arch = custom_arch

    if not arch:
        raise Exception(f'Could not determine architecture for {path_to_analyze}')

    # Overwrite the automatically-derived project class if one is provided
    if project_class:
        if not issubclass(project_class, AbstractProject):
            raise Exception('Custom projects must be a subclass of AbstractProject')
        proj_class = project_class

    return Target(path, args, arch, op_sys, aux_files), proj_class


def _handle_with_file(target_path, target_args, proj_class, *args, **options):
    arch = options.get('arch', None)
    if arch and arch not in SUPPORTED_ARCHS:
        raise Exception(f'Architecture {arch} is not supported')

    target, proj_class = target_from_file(target_path, target_args, proj_class, arch)
    options['target'] = target

    return call_command(proj_class(), *args, **options)


def _get_project_class(**options):
    project_types = list(PROJECT_TYPES.keys())
    if options['type'] not in project_types:
        raise CommandError('An empty project requires a type. Use the -t '
                            'option and specify one from %s' % project_types)
    return PROJECT_TYPES[options['type']]


def _handle_empty_project(proj_class, *args, **options):
    if not proj_class:
        raise CommandError('Please specify a project type')

    if not options['no_target']:
        raise CommandError('No target binary specified. Use the -m option to '
                           'create an empty project')

    if not options['image']:
        raise CommandError('An empty project requires a VM image. Use the -i '
                           'option to specify the image')

    if not options['name']:
        raise CommandError('An empty project requires a name. Use the -n '
                           'option to specify one')

    options['target'] = Target.empty()

    return call_command(proj_class(), *args, **options)


class Command(EnvCommand):
    """
    Initialize a new analysis project.
    """

    help = 'Initialize a new analysis project.'

    def add_arguments(self, parser):
        super().add_arguments(parser)

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
                            help='Create an empty, target-less project. Used '
                                 'when no binary is needed')

        project_types_keys = ','.join(list(PROJECT_TYPES.keys()))
        parser.add_argument('-t', '--type', required=False, default=None,
                            help=f'Project type ({project_types_keys}), valid only when creating empty projects')

        parser.add_argument('-s', '--use-seeds', action='store_true',
                            help='Use this option to use seeds for creating '
                                 'symbolic files. Users must create these '
                                 'seeds themselves and place them in the '
                                 'project\'s ``seeds`` directory')

        parser.add_argument('--arch', required=False, default=None,
                            help='Architecture for binaries whose architecture cannot be autodetected. '
                                 f'Supported architectures: {SUPPORTED_ARCHS}')

        parser.add_argument('--tools', type=lambda s: s.split(','),
                            default=[],
                            help='Comma-separated list of tools to enable '
                                 f'(supported tools: {",".join(SUPPORTED_TOOLS)})')

        parser.add_argument('--single-path', action='store_true', default=False,
                            help='Enables single-path mode, no symbolic execution possible')

        parser.add_argument('-a', '--sym-args', type=_parse_sym_args, default='',
                            help='A space-separated list of target argument '
                                 'indices to make symbolic')

        parser.add_argument('-f', '--force', action='store_true',
                            help='If a project with the given name already '
                                 'exists, replace it')

    def handle(self, *args, **options):
        if not validate_arguments(options):
            return

        # The 'project_class' option is not exposed as a command-line argument:
        # it is typically used when creating a custom project programmatically.
        # It provides a class that is instantiated with the current
        # command-line arguments and options
        proj_class = options.pop('project_class', None)

        if options['target']:
            _handle_with_file(options.pop('target'), options.pop('target_args'), proj_class, *args, **options)
        else:
            _handle_empty_project(proj_class, *args, **options)

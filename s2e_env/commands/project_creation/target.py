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
import re

from magic import Magic

from s2e_env.infparser.driver import Driver

from .abstract_project import AbstractProject
from .cgc_project import CGCProject
from .linux_project import LinuxProject
from .windows_project import WindowsProject, WindowsDLLProject, WindowsDriverProject


logger = logging.getLogger('new_project')

# Paths
FILE_DIR = os.path.dirname(__file__)
CGC_MAGIC = os.path.join(FILE_DIR, '..', '..', 'dat', 'cgc.magic')

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
        (Magic(magic_file=CGC_MAGIC), CGC_REGEX, CGCProject, 'i386', 'decree'),
        (default_magic, ELF32_REGEX, LinuxProject, 'i386', 'linux'),
        (default_magic, ELF64_REGEX, LinuxProject, 'x86_64', 'linux'),
        (default_magic, DLL32_REGEX, WindowsDLLProject, 'i386', 'windows'),
        (default_magic, DLL64_REGEX, WindowsDLLProject, 'x86_64', 'windows'),
        (default_magic, WIN32_DRIVER_REGEX, WindowsDriverProject, 'i386', 'windows'),
        (default_magic, WIN64_DRIVER_REGEX, WindowsDriverProject, 'x86_64', 'windows'),
        (default_magic, PE32_REGEX, WindowsProject, 'i386', 'windows'),
        (default_magic, PE64_REGEX, WindowsProject, 'x86_64', 'windows'),
        (default_magic, MSDOS_REGEX, WindowsProject, 'i386', 'windows'),
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
        raise TargetError('Driver has no files')

    base_dir = os.path.dirname(target_path)

    logger.info('  Driver files:')
    file_paths = []
    for f in driver_files:
        full_path = os.path.join(base_dir, f)
        if not os.path.exists(full_path):
            if full_path.endswith('.cat'):
                logger.warning('Catalog file %s is missing', full_path)
                continue
            raise TargetError('%s does not exist' % full_path)

        logger.info('    %s', full_path)
        file_paths.append(full_path)

    return list(set(file_paths))


class TargetError(Exception):
    """An error occurred when creating a new S2E analysis target."""


class Target:
    """
    Encapsulates a program (e.g., executable, driver, DLL, etc.) to be analyzed
    by S2E.
    """

    @staticmethod
    def from_file(path, project_class=None):
        # Check that the target is a valid file
        if not os.path.isfile(path):
            raise TargetError('Target %s does not exist' % path)

        if path.endswith('.inf'):
            logger.info('Detected Windows INF file, attempting to create a '
                        'driver project...')
            driver_files = _extract_inf_files(path)

            first_sys_file = None
            for f in driver_files:
                if f.endswith('.sys'):
                    first_sys_file = f

            # TODO: prompt the user to select the right driver
            if not first_sys_file:
                raise TargetError('Could not find a *.sys file in the INF '
                                  'file. Make sure that the INF file is valid '
                                  'and belongs to a Windows driver')

            path_to_analyze = first_sys_file
            aux_files = driver_files
        else:
            path_to_analyze = path
            aux_files = []

        arch, operating_sys, proj_class = _determine_arch_and_proj(path_to_analyze)
        if not arch:
            raise TargetError('Could not determine architecture for %s' %
                              path_to_analyze)

        # Overwrite the automatically-derived project class if one is provided
        if project_class:
            if not issubclass(project_class, AbstractProject):
                raise TargetError('Custom projects must be a subclass of '
                                  '`AbstractProject`')
            proj_class = project_class

        return Target(path, arch, operating_sys, proj_class, aux_files)

    @staticmethod
    def empty(project_class):
        """Create an empty target."""
        return Target(None, None, None, project_class)

    # pylint: disable=too-many-arguments
    def __init__(self, path, arch, operating_sys, project_class, aux_files=None):
        """
        This constructor should not be called directly. Rather, the
        ``from_file`` or ``empty`` static methods should be used to create a
        ``Target``.
        """
        self._path = path
        self._arch = arch
        self._os = operating_sys
        self._proj_class = project_class

        if not aux_files:
            aux_files = []

        self._aux_files = aux_files

    @property
    def path(self):
        """The path of the program under analysis."""
        return self._path

    @property
    def arch(self):
        """
        The architecture (e.g., i386, x86-64, etc.) of the program under
        analysis.
        """
        return self._arch

    @property
    def operating_system(self):
        """The operating system that the target executes on."""
        return self._os

    @property
    def aux_files(self):
        """
        A list of any auxillary files required by S2E to analysis the target
        program.
        """
        return self._aux_files

    def initialize_project(self):
        """Initialize an s2e-env analysis project for this target."""
        return self._proj_class()

    def is_empty(self):
        """Returns ``True`` if the target is an empty one."""
        return not self._path

    def __str__(self):
        return 'Target(path=%s,arch=%s)' % (self._path, self._arch)

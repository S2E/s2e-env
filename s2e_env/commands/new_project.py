"""
MIT License

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
from projects.cgc import CGCProject
from projects.linux import LinuxProject
from projects.windows import WindowsProject

# Paths
FILE_DIR = os.path.dirname(__file__)
CGC_MAGIC = os.path.join(FILE_DIR, '..', 'dat', 'cgc.magic')

# Magic regexs
CGC_REGEX = re.compile(r'^CGC 32-bit')
ELF32_REGEX = re.compile(r'^ELF 32-bit')
ELF64_REGEX = re.compile(r'^ELF 64-bit')
PE32_REGEX = re.compile(r'^PE executable')
PE64_REGEX = re.compile(r'^PE\+ executable')


#
# The actual command class to execute from the command line
#
class Command(EnvCommand):
    """
    Initialize a new analysis project.
    """

    help = 'Initialize a new analysis project.'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('target', nargs='?',
                            help='Path to the target file to analyze. You may '
                                 'leave this empty, in which case an empty '
                                 'Linux project will be created')
        parser.add_argument('target_args', nargs=argparse.REMAINDER,
                            help='Arguments to the target program')
        parser.add_argument('-n', '--name', required=False, default=None,
                            help='The name of the project. Defaults to the '
                                 'name of the target program. If you are '
                                 'creating an empty project then this field '
                                 'must be specified')
        parser.add_argument('-i', '--image', required=True,
                            help='The name of an image in the ``images`` '
                                 'directory (without a file extension)')
        parser.add_argument('-s', '--use-seeds', action='store_true',
                            help='Use this option to use seeds for creating '
                                 'concolic files. The user must create these '
                                 'seeds themselves and place them in the '
                                 'project\'s ``seeds`` directory')
        parser.add_argument('-f', '--force', action='store_true',
                            help='If a project with the given name already '
                                 'exists, replace it')

    def handle(self, **options):
        # Need an absolute path for the target in order to simplify
        # symlink creation.
        target_path = options['target']
        target_path = os.path.abspath(target_path)
        options['target'] = target_path

        magic_checks = [
            (Magic(magic_file=CGC_MAGIC), CGC_REGEX, CGCProject, 'i386'),
            (Magic(), ELF32_REGEX, LinuxProject, 'i386'),
            (Magic(), ELF64_REGEX, LinuxProject, 'x86_64'),
            (Magic(), PE32_REGEX, WindowsProject, 'i386'),
            (Magic(), PE64_REGEX, WindowsProject, 'x86_64'),
        ]

        # Check the target program against the valid file types
        for magic_check, regex, proj_class, arch in magic_checks:
            magic = magic_check.from_file(target_path)
            matches = regex.match(magic)

            # If we find a match, create that project. The user instructions
            # are returned
            if matches:
                options['target_arch'] = arch
                return call_command(proj_class(), **options)

        # Otherwise no valid file type was found
        raise CommandError('%s is not a valid target for S2E analysis' %
                           target_path)

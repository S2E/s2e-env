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

from s2e_env.command import EnvCommand, CommandError
from s2e_env.commands.project_creation import CGCProject
from s2e_env.commands.project_creation import LinuxProject
from s2e_env.commands.project_creation import WindowsProject, \
        WindowsDLLProject, WindowsDriverProject
from s2e_env.commands.project_creation import Target
from s2e_env.manage import call_command


logger = logging.getLogger('new_project')

PROJECT_TYPES = {
    'cgc': CGCProject,
    'linux': LinuxProject,
    'windows': WindowsProject,
    'windows_dll': WindowsDLLProject,
    'windows_driver': WindowsDriverProject,
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


def _handle_with_file(target_path, proj_class, *args, **options):
    target = Target.from_file(target_path, proj_class)
    options['target'] = target

    return call_command(target.initialize_project(), *args, **options)


def _handle_empty_project(proj_class, *args, **options):
    if not options['no_target']:
        raise CommandError('No target binary specified. Use the -m option to '
                           'create an empty project')

    if not options['image']:
        raise CommandError('An empty project requires a VM image. Use the -i '
                           'option to specify the image')

    if not options['name']:
        raise CommandError('An empty project requires a name. Use the -n '
                           'option to specify one')

    # If the project class wasn't explicitly overridden programmatically, get
    # one of the default project classes from the command line
    if not proj_class:
        project_types = list(PROJECT_TYPES.keys())
        if options['type'] not in project_types:
            raise CommandError('An empty project requires a type. Use the -t '
                               'option and specify one from %s' % project_types)
        proj_class = PROJECT_TYPES[options['type']]

    target = Target.empty(proj_class)
    options['target'] = target

    return call_command(target.initialize_project(), *args, **options)


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
                            help='Create an empty, target-less project. Used '
                                 'when no binary is needed')

        parser.add_argument('-t', '--type', required=False, default=None,
                            help='Project type (%s), valid only when creating empty projects' %
                            ','.join(list(PROJECT_TYPES.keys())))

        parser.add_argument('-s', '--use-seeds', action='store_true',
                            help='Use this option to use seeds for creating '
                                 'symbolic files. The user must create these '
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
        proj_class = options.pop('project_class', None)
        if options['target']:
            _handle_with_file(options.pop('target'), proj_class, *args, **options)
        else:
            _handle_empty_project(proj_class, *args, **options)

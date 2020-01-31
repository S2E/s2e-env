"""
Copyright (c) Django Software Foundation and individual contributors.
Copyright (c) Dependable Systems Laboratory, EPFL
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice,
       this list of conditions and the following disclaimer.

    2. Redistributions in binary form must reproduce the above copyright
       notice, this list of conditions and the following disclaimer in the
       documentation and/or other materials provided with the distribution.

    3. Neither the name of Django nor the names of its contributors may be used
       to endorse or promote products derived from this software without
       specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""


from abc import ABCMeta, abstractmethod
from argparse import ArgumentParser
import json
import logging
import os
import sys

import yaml

class CommandError(Exception):
    """
    Exception class indicating a problem while executing a command.

    If this exception is raised during the execution of a command, it will be
    caught and turned into a nicely-printed error message to the appropriate
    output stream (i.e. stderr); as a result raising this exception (with a
    sensible description of the error) is the preferred way to indicate that
    something has gone wrong in the execution of the command.
    """


class CommandParser(ArgumentParser):
    """
    Customized ``ArgumentParser`` class to improve some error messages and
    prevent SystemExit in several occasions, as SystemExit is unacceptable
    when a command is called programmatically.
    """
    def __init__(self, cmd, **kwargs):
        self._cmd = cmd
        super(CommandParser, self).__init__(**kwargs)

    def error(self, message):
        if self._cmd.called_from_command_line:
            super(CommandParser, self).error(message)
        else:
            raise CommandError(message)


class BaseCommand(metaclass=ABCMeta):
    """
    The base class that all commands ultimately derive from.

    This class is based on Django's ``BaseCommand`` class. The normal flow
    works as follows:

    1. ``manage.py`` loads the command class and calls its ``run_from_argv()``
       method.

    2.  The ``run_from_argv()`` method calls ``create_parser()`` to get an
        ``ArgumentParser`` for the arguments, parses them and then calls the
        ``execute()`` method, passing the parsed arguments.

    3. The ``execute`` method attemps to carry out the command by calling the
       ``handle()`` method with the parsed arguments.

    4. If ``handle()`` or ``execute()`` raises an exception (e.g.
       ``CommandError``), ``run_from_argv()`` will instead print an error
       message to ``stderr``.

    Thus, the ``handle`` method is typically the starting point for subclasses;
    many built-in commands either place all of their logic in ``handle()``, or
    perform some additional parsing work in ``handle()`` and then delegate from
    it to more specialized methods as needed. The handle method can return a
    string that will be printed on sucessful completion of the command.

    If a subclass requires additional arguments and options, these should be
    implemented in the ``add_arguments()`` method. For specifying a short
    description of the command, which will be printed in help messages, the
    ``help`` class attribute should be specified.
    """

    # Metadata about this command
    help = ''

    # Configuration shortcuts that alter various logic.
    called_from_command_line = False

    def create_parser(self, prog_name, subcommand):
        """
        Create and return the ``CommandParser`` which will be used to parse
        the arguments to this command.
        """
        parser = CommandParser(
            self, prog='%s %s' % (os.path.basename(prog_name), subcommand),
            description=self.help or None)

        # Add any arguments that all commands should accept here
        self.add_arguments(parser)

        return parser

    def add_arguments(self, parser):
        """
        Entry point for subclassed commands to add custom arguments.
        """

    def print_help(self, prog_name, subcommand):
        """
        Print the help message for this command, derived from ``self.usage()``.
        """
        parser = self.create_parser(prog_name, subcommand)
        parser.print_help()

    def run_from_argv(self, argv):
        """
        Run this command. If the command raises an ``CommandError``, intercept
        it and print it sensibly to stderr.
        """
        self.called_from_command_line = True
        parser = self.create_parser(argv[0], argv[1])

        options = parser.parse_args(argv[2:])
        cmd_options = vars(options)
        # Move positional args out of options to mimic legacy optparse
        args = cmd_options.pop('args', ())

        try:
            if not os.getuid():
                raise CommandError('Please do not run s2e as root')

            self.execute(*args, **cmd_options)
        except Exception as e:
            # Only handle CommandErrors here
            if not isinstance(e, CommandError):
                raise

            logger = logging.getLogger(self.name)
            logger.error(e)
            sys.exit(1)

    def handle_common_args(self, **options):
        """
        Handle any common command options here and remove them from the options
        dict given to the command.
        """

    def execute(self, *args, **options):
        """
        Try to execute the command.
        """
        self.handle_common_args(**options)

        self.handle(*args, **options)

    @property
    def name(self):
        return self.__module__.split('.')[-1]

    @abstractmethod
    def handle(self, *args, **options):
        """
        The actual logic of the command. Subclasses must implement this method.
        """
        raise NotImplementedError('subclasses of BaseCommand must provide a '
                                  'handle() method')

# pylint: disable=abstract-method
# We don't want to implement handle() in this class
class EnvCommand(BaseCommand):
    """
    The base command for all commands that follow the ``init`` command.

    This is just a convenience class to reduce duplicate code.
    """

    def __init__(self):
        super(EnvCommand, self).__init__()

        self._env_dir = None
        self._config = None

    def handle_common_args(self, **options):
        """
        Adds the environment directory as a class member.

        The environment directory is specified as either an environment
        variable or a command-line option.
        """
        self._env_dir = os.getenv('S2EDIR') or options.pop('env')

        if not self._env_dir:
            raise CommandError('The S2E environment directory could not be '
                               'determined. Source install/bin/s2e_activate '
                               'in your environment or use the --env option')

        try:
            path = self.env_path('s2e.yaml')
            with open(path, 'r') as f:
                self._config = yaml.safe_load(f)
        except IOError:
            raise CommandError('This does not look like an S2E environment - '
                               'it does not contain an s2e.yaml configuration '
                               'file (%s does not exist). Source %s in your '
                               'environment' % (path, self.env_path('s2e_activate')))

    def add_arguments(self, parser):
        super(EnvCommand, self).add_arguments(parser)

        parser.add_argument('-e', '--env', required=False, default=os.getcwd(),
                            help='The S2E environment. Only used if the '
                                 'S2EDIR environment variable is not defined. '
                                 'Defaults to the current working directory')

    @property
    def config(self):
        """
        Get the configuration dictionary.
        """
        return self._config

    def env_path(self, *p):
        """
        Create a path relative to the environment directory.
        """
        return os.path.join(self._env_dir, *p)

    def install_path(self, *p):
        """
        Create a path relative to the S2E install directory.
        """
        return self.env_path('install', *p)

    def projects_path(self, *p):
        """
        Create a path relative to the S2E projects directory.
        """
        return self.env_path('projects', *p)

    def build_path(self, *p):
        """
        Create a path relative to the S2E install directory.
        """
        return self.env_path('build', 's2e', *p)

    def source_path(self, *p):
        """
        Create a path relative to the source directory.
        """
        return self.env_path('source', *p)

    def image_path(self, *p):
        """
        Create a path relative to the image directory.
        """
        return self.env_path('images', *p)


# pylint: disable=abstract-method
# We don't want to implement handle() in this class
class ProjectCommand(EnvCommand):
    """
    The base command for all commands that work on existing projects.

    This is another convenience class to reduce duplicate code.
    """

    def __init__(self):
        super(ProjectCommand, self).__init__()

        self._project_dir = None
        self._project_desc = None
        self._project_name = None
        self._sym_paths = []
        self._image = None

    def handle_common_args(self, **options):
        """
        Adds the project directory as a class member.
        """
        super(ProjectCommand, self).handle_common_args(**options)

        # Construct the project directory
        self._project_dir = self.env_path('projects', options['project'])
        self._project_name = options.pop('project', ())

        # Load the project description
        try:
            proj_desc_path = os.path.join(self._project_dir, 'project.json')
            with open(proj_desc_path, 'r') as f:
                self._project_desc = json.load(f)
        except IOError:
            raise CommandError('%s does not look like an S2E analysis '
                               'project - it does not contain a project.json '
                               'project description. Please check the project '
                               'name' % self._project_name)

        # Load the additional symbol paths
        self._sym_paths = options.pop('sympath')

    def add_arguments(self, parser):
        super(ProjectCommand, self).add_arguments(parser)

        parser.add_argument('project', help='The name of the project')
        parser.add_argument('--sympath', action='append', required=False,
                            default=[], help='Additional symbol search path')

    def project_path(self, *p):
        """
        Create a path relative to this project directory.
        """
        return os.path.join(self._project_dir, *p)

    @property
    def symbol_search_path(self):
        # guestfs should come last because it may contain outdated and
        # conflicting copies of guest-tools
        default_paths = [self.project_path(), self.project_path('guest-tools'),
                         self.project_path('guestfs')]

        return default_paths + self._sym_paths

    @property
    def project_name(self):
        """
        Get the project name.
        """
        return self._project_name

    @property
    def project_desc(self):
        """
        Get the project descriptor dictionary.
        """
        return self._project_desc

    @property
    def image(self):
        # Put import here to avoid circular dependency
        # https://github.com/PyCQA/pylint/issues/850
        # pylint: disable=cyclic-import
        # pylint: disable=import-outside-toplevel
        from s2e_env.utils import images

        if not self._image:
            self._image = images.get_image_descriptor(self.project_desc['image'])
        return self._image

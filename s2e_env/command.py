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


from argparse import ArgumentParser
import json
import os
import sys

from s2e_env.utils.terminal import print_info
from s2e_env.utils.terminal import print_success
from s2e_env.utils.terminal import print_warn
from s2e_env.utils.terminal import print_error


class CommandError(Exception):
    """
    Exception class indicating a problem while executing a command.

    If this exception is raised during the execution of a command, it will be
    caught and turned into a nicely-printed error message to the appropriate
    output stream (i.e. stderr); as a result raising this exception (with a
    sensible description of the error) is the preferred way to indicate that
    something has gone wrong in the execution of the command.
    """
    pass


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


class BaseCommand(object):
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

    When writting new commands, the author may use one of ``info()``,
    ``warn()`` or ``error()`` to print out messages. Note that whether these
    messages are displayed is dependent on the verbosity level set.
    """
    # Metadata about this command
    help = ''

    # Configuration shortcuts that alter various logic.
    called_from_command_line = False

    def __init__(self):
        self._verbosity = 1

    def create_parser(self, prog_name, subcommand):
        """
        Create and return the ``CommandParser`` which will be used to parse
        the arguments to this command.
        """
        parser = CommandParser(
            self, prog='%s %s' % (os.path.basename(prog_name), subcommand),
            description=self.help or None)

        # Add any arguments that all commands should accept here
        parser.add_argument('-v', '--verbosity', type=int, default=1,
                            choices=[0, 1, 2],
                            help='Verbosity level; 0=minimal output, '
                                 '1=normal output, 2=verbose output')
        self.add_arguments(parser)

        return parser

    def add_arguments(self, parser):
        """
        Entry point for subclassed commands to add custom arguments.
        """
        pass

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
            output = self.execute(*args, **cmd_options)
        except Exception as e:
            # Only handle CommandErrors here
            if not isinstance(e, CommandError):
                raise

            self.error(e)
            sys.exit(1)

        return output

    def handle_common_args(self, options):
        """
        Handle any common command options here and remove them from the options
        dict given to the command.
        """
        self._verbosity = options['verbosity']
        options.pop('verbosity', ())

    def execute(self, *args, **options):
        """
        Try to execute the command.
        """
        self.handle_common_args(options)

        success_msg = self.handle(*args, **options)
        if success_msg:
            self.success(success_msg)

    @property
    def name(self):
        return self.__module__.split('.')[-1]

    def info(self, msg):
        """
        Print an info message to stdout.
        """
        if self._verbosity >= 1:
            print_info('[%s] %s' % (self.name, msg))

    def success(self, msg):
        """
        Print a success message to stdout.
        """
        if self._verbosity >= 1:
            print_success('[%s] %s' % (self.name, msg))

    def warn(self, msg):
        """
        Print a warning message to stdout.
        """
        if self._verbosity >= 1:
            print_warn('[%s] %s' % (self.name, msg))

    def error(self, msg):
        """
        Print an error message to stderr.
        """
        # Always print errors regardless of verbosity
        print_error('[%s] %s' % (self.name, msg))

    def handle(self, *args, **options):
        """
        The actual logic of the command. Subclasses must implement this method.
        """
        raise NotImplementedError('subclasses of BaseCommand must provide a '
                                  'handle() method')


class EnvCommand(BaseCommand):
    """
    The base command for all commands that follow the ``init`` command.

    This is just a convenience class to reduce duplicate code.
    """

    def __init__(self):
        super(EnvCommand, self).__init__()

        self._env_dir = None

    def handle_common_args(self, options):
        """
        Adds the environment directory as a class member.
        """
        super(EnvCommand, self).handle_common_args(options)

        self._env_dir = options['env']
        options.pop('env', ())

        try:
            with open(self.s2eenv_path()):
                pass
        except IOError:
            raise CommandError('This does not look like an S2E project directory.')

    def add_arguments(self, parser):
        parser.add_argument('-e', '--env', default=os.getcwd(), required=False,
                            help='The S2E development environment. Defaults '
                                 'to the current working directory')

    def s2eenv_path(self):
        return self.env_path('.s2eenv')

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

    def build_path(self, *p):
        """
        Create a path relative to the S2E install directory
        """
        return os.path.join(self._env_dir, 'build', 's2e', *p)

    def source_path(self, *p):
        """
        Create a path relative to the source directory
        """
        return os.path.join(self._env_dir, 'source', *p)

    def image_path(self, *p):
        """
        Create a path relative to the image directory
        """
        return os.path.join(self._env_dir, 'images', *p)

class ProjectCommand(EnvCommand):
    """
    The base command for all commands that work on existing projects.

    This is another convenience class to reduce duplicate code.
    """

    def __init__(self):
        super(ProjectCommand, self).__init__()

        self._project_dir = None
        self._project_desc = None

    def handle_common_args(self, options):
        """
        Adds the project directory as a class member.
        """
        super(ProjectCommand, self).handle_common_args(options)

        # Construct the project directory
        self._project_dir = self.env_path('projects', options['project'])
        options.pop('project', ())

        # Load the project description
        try:
            proj_desc_path = os.path.join(self._project_dir, 'project.json')
            with open(proj_desc_path, 'r') as f:
                self._project_desc = json.load(f)
        except Exception as e:
            raise CommandError('Unable to open project description for %s - '
                               '%s' % (os.path.basename(self._project_dir), e))

    def add_arguments(self, parser):
        super(ProjectCommand, self).add_arguments(parser)

        parser.add_argument('project', help='The name of the project')

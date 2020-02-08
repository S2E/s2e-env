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


import os
import pkgutil
import importlib
import sys

from s2e_env.command import BaseCommand, CommandError, CommandParser
from s2e_env.utils import log


COMMANDS_DIR = os.path.join(os.path.dirname(__file__), 'commands')


def find_commands():
    """
    Give a path to a management directory, returns a list of all the command
    names that are available.

    Returns an empty list if no commands are defined.
    """
    return [name for _, name, ispkg in pkgutil.iter_modules([COMMANDS_DIR])
            if not ispkg and not name.startswith('_')]


def load_command_class(name):
    """
    Given a command name, returns the Command class instance. All errors raised
    by the import process (ImportError, AttributeError) are allowed to
    propagate.
    """
    module = importlib.import_module('s2e_env.commands.%s' % name)
    return module.Command()


def call_command(command_name, *args, **options):
    """
    Call the given command, with the given options and args/kwargs.

    This is the primary API you should use for calling specific commands.

    `name` may be a string or a command object. Using a string is preferred
    unless the command object is required for further processing or testing.
    """
    if isinstance(command_name, BaseCommand):
        # Command object passed in
        command = command_name
        command_name = command.__class__.__module__.split('.')[-1]
    else:
        # Load the command object by name
        command = load_command_class(command_name)

    # Simulate argument parsing to get the option defaults
    parser = command.create_parser('', command_name)
    # Use the `dest` option name from the parser option

    # pylint: disable=protected-access
    opt_mapping = {
        min(s_opt.option_strings).lstrip('-').replace('-', '_'): s_opt.dest
        for s_opt in parser._actions if s_opt.option_strings
    }
    arg_options = {opt_mapping.get(key, key): value for
                   key, value in options.items()}
    defaults = parser.parse_args(args=args)

    # pylint: disable=protected-access
    defaults = dict(defaults._get_kwargs(), **arg_options)

    # Move positional args out of options to mimic legacy optparse
    args = defaults.pop('args', ())

    return command.execute(*args, **defaults)


class CommandManager:
    """
    Manages and executes commands.
    """
    def __init__(self, argv):
        # We must do a copy by value of the arguments, because the original sys.argv
        # may be sometimes changed arbitrarily by a call to import_module.
        self._argv = argv[:]
        self._prog_name = os.path.basename(self._argv[0])

    def main_help_text(self, commands_only=False):
        """
        Return's the main help text, as a string.
        """
        if commands_only:
            usage = sorted(find_commands())
        else:
            usage = [
                '',
                'Type \'%s help <subcommand>\' for help on a specific '
                'subcommand.' % self._prog_name,
                '',
                'Available subcommands:',
            ]
            for command in find_commands():
                usage.append('    %s' % command)

        return '\n'.join(usage)

    def fetch_command(self, subcommand):
        """
        Tries to fetch the given subcommand, printing a message with the
        appropriate command called from the command line if it can't be found.
        """
        commands = find_commands()
        if subcommand not in commands:
            sys.stderr.write('Unknown command - %r. Type \'%s help\' for '
                             'usage\n' % (subcommand, self._prog_name))
            sys.exit(1)

        return load_command_class(subcommand)

    def execute(self):
        """
        Given the command-line arguments, this figures out which subcommand is
        being run, creates a parser appropriate to that command, and runs it.
        """
        try:
            subcommand = self._argv[1]
        except IndexError:
            subcommand = 'help' # Display help if no arguments were given

        parser = CommandParser(None,
                               usage='%(prog)s subcommand [options] [args]',
                               add_help=False)
        parser.add_argument('args', nargs='*') # catch-all

        try:
            options, args = parser.parse_known_args(self._argv[2:])
        except CommandError:
            pass # Ignore any option errors at this point

        if subcommand == 'help':
            if '--commands' in args:
                sys.stdout.write('%s\n' %
                                 self.main_help_text(commands_only=True))
            elif len(options.args) < 1:
                sys.stdout.write('%s\n' % self.main_help_text())
            else:
                self.fetch_command(options.args[0]).print_help(self._prog_name,
                                                               options.args[0])
        elif self._argv[1:] in (['--help'], ['-h']):
            sys.stdout.write('%s\n' % self.main_help_text())
        else:
            self.fetch_command(subcommand).run_from_argv(self._argv)


def main():
    """
    The main function.

    Use the command manager to execute a command.
    """
    log.configure_logging()
    manager = CommandManager(sys.argv)
    manager.execute()


if __name__ == '__main__':
    main()

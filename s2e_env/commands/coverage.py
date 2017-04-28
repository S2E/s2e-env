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


from s2e_env.command import ProjectCommand
from s2e_env.manage import call_command
from s2e_env.commands.code_coverage.basic_block import BasicBlockCoverage
from s2e_env.commands.code_coverage.lcov import LineCoverage


class Command(ProjectCommand):
    """
    Analyze coverage information from S2E.
    """

    help = 'Analyze S2E code coverage. This includes both basic block and ' \
           'line coverage.'

    def __init__(self):
        super(Command, self).__init__()

        self._lcov = LineCoverage()
        self._basic_block = BasicBlockCoverage()

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(help='Coverage report type',
                                           dest='command')

        subparsers.add_parser('lcov', cmd=self._lcov,
                              help='Generate a line coverage report')

        subparsers.add_parser('basic_block', cmd=self._basic_block,
                              help='Generate a basic block report')

        super(Command, self).add_arguments(parser)

    def handle(self, *args, **options):
        command = options.pop('command', ())

        if command == 'basic_block':
            return call_command(self._basic_block, [], **options)
        elif command == 'lcov':
            return call_command(self._lcov, [], **options)

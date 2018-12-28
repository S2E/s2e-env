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


from s2e_env.command import ProjectCommand, CommandError
from s2e_env.commands.code_coverage.lcov import LineCoverage
from s2e_env.manage import call_command

from .code_coverage.ida_basic_block import IDABasicBlockCoverage
from .code_coverage.r2_basic_block import R2BasicBlockCoverage
from .code_coverage.binaryninja_basic_block import BinaryNinjaBasicBlockCoverage


class Command(ProjectCommand):
    """
    Analyze coverage information from S2E.
    """

    help = 'Analyze S2E code coverage. This includes both basic block and ' \
           'line coverage.'

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(help='Coverage report type',
                                           dest='command')

        lcov_parser = subparsers.add_parser('lcov', cmd=LineCoverage(),
                                            help='Generate a line coverage report')
        lcov_parser.add_argument('--html', action='store_true',
                                 help='Generate an HTML report in s2e-last')
        lcov_parser.add_argument('--include-covered-files-only', action='store_true',
                                 help='The coverage report will exclude files that were never covered', default=True)

        lcov_parser.add_argument('--s2e-out-dir', action='append',
                                 help='S2E output directories to consider (default is s2e-last).',
                                 required=False)

        lcov_parser.add_argument('--aggregate-outputs', type=int,
                                 help='Specifies n most recent s2e-out-* folders to aggregate for coverage.',
                                 required=False)

        lcov_parser.add_argument('--lcov-out-dir', type=str,
                                 help='Where to store the LCOV report (by default into s2e-last)',
                                 required=False)

        bb_parser = subparsers.add_parser('basic_block', cmd=IDABasicBlockCoverage(),
                                          help='Generate a basic block report')
        bb_parser.add_argument('-d', '--disassembler', choices=('ida', 'r2', 'binaryninja'),
                               default='ida', help='Disassembler backend to use')
        bb_parser.add_argument('-r', '--drcov', action='store_true',
                               help='Generate drcov-compatible output')

        super(Command, self).add_arguments(parser)

    def handle(self, *args, **options):
        command = options.pop('command', ())

        if command == 'basic_block':
            # Select the disassembler backend
            disassembler = options.pop('disassembler', ())
            if disassembler == 'ida':
                call_command(IDABasicBlockCoverage(), args, **options)
            elif disassembler == 'r2':
                call_command(R2BasicBlockCoverage(), args, **options)
            elif disassembler == 'binaryninja':
                call_command(BinaryNinjaBasicBlockCoverage(), args, **options)
        elif command == 'lcov':
            call_command(LineCoverage(), args, **options)
        else:
            raise CommandError('Invalid command %s' % command)

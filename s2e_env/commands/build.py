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


import os
import sys

import sh
from sh import ErrorReturnCode

from s2e_env.command import EnvCommand, CommandError


class Command(EnvCommand):
    """
    Builds S2E.
    """

    help = 'Build S2E.'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('-g', '--debug', action='store_true',
                            help='Build S2E in debug mode')

    def handle(self, *args, **options):
        # Exit if the makefile doesn't exist
        makefile = self.env_path('source', 's2e', 'Makefile')
        if not os.path.isfile(makefile):
            raise CommandError('No makefile found in %s' %
                               os.path.dirname(makefile))

        # If the build directory doesn't exist, create it
        build_dir = self.env_path('build', 's2e')
        if not os.path.isdir(build_dir):
            os.mkdir(build_dir)

        try:
            # Set up some environment variables
            env_vars = os.environ.copy()
            env_vars['S2EPREFIX'] = self.install_path()

            # Run make
            make = sh.Command('make').bake(directory=build_dir, file=makefile,
                                           _out=sys.stdout, _err=sys.stderr,
                                           _env=env_vars, _fg=True)

            if options['debug']:
                self.info('Building S2E (debug) in %s' % build_dir)
                make('all-debug')
            else:
                self.info('Building S2E (release) in %s' % build_dir)
                make('install')
        except ErrorReturnCode as e:
            raise CommandError(e)

        return 'S2E built'

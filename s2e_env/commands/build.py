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

    def handle(self, **options):
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
            env_vars['S2EPREFIX'] = self._env_dir

            # Run make
            make = sh.Command('make').bake(directory=build_dir, file=makefile,
                                           _out=sys.stdout, _err=sys.stderr,
                                           _env=env_vars, _fg=True)

            if options['debug']:
                self.info('Building S2E (debug) in %s' % build_dir)
                make('install-debug')
            else:
                self.info('Building S2E (release) in %s' % build_dir)
                make('install')
        except ErrorReturnCode as e:
            raise CommandError(e)

        return 'S2E built'

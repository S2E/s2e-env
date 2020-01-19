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


import glob
import logging
import os
import sys

import sh
from sh import ErrorReturnCode

from s2e_env.command import EnvCommand, CommandError


logger = logging.getLogger('build')


class Command(EnvCommand):
    """
    Builds S2E.

    This command also allows the user to specify a list of S2E components (e.g.
    QEMU, libs2e, Z3, etc.) to force a rebuild for.
    """

    help = 'Build S2E.'

    def __init__(self):
        super(Command, self).__init__()

        self._make = None

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('-g', '--debug', action='store_true',
                            help='Build S2E in debug mode')
        parser.add_argument('-r', '--rebuild-components', nargs='+',
                            required=False, dest='components',
                            help='List of S2E components to clean prior to '
                                 'the build process')

    def handle(self, *args, **options):
        # Exit if the makefile doesn't exist
        makefile = self.env_path('source', 'Makefile')
        if not os.path.isfile(makefile):
            raise CommandError('No makefile found in %s' %
                               os.path.dirname(makefile))

        # If the build directory doesn't exist, create it
        build_dir = self.env_path('build')
        if not os.path.isdir(build_dir):
            os.mkdir(build_dir)

        # Set up some environment variables
        env_vars = os.environ.copy()
        env_vars['S2E_PREFIX'] = self.install_path()

        components = options['components']
        self._make = sh.Command('make').bake(directory=build_dir, file=makefile, _env=env_vars)

        # If the user has specified any components to rebuild, do this before
        # the build
        if components:
            self._rebuild_components(components)

        try:
            # Run make
            if options['debug']:
                logger.info('Building S2E (debug) in %s', build_dir)
                self._make('all-debug', _out=sys.stdout, _err=sys.stderr, _fg=True)
            else:
                logger.info('Building S2E (release) in %s', build_dir)
                self._make('install', _out=sys.stdout, _err=sys.stderr, _fg=True)
        except ErrorReturnCode as e:
            raise CommandError(e)

        logger.success('S2E built')

    def _rebuild_components(self, components):
        """
        Cleans components to force them to be rebuilt.

        After successfully building an S2E component (e.g. QEMU, libs2e, Z3,
        etc.), the S2E Makefile will create a "stamp" in the S2E build
        directory. Subsequent builds will first check if a component's stamp
        exists, and if it does the build process will not rebuild. To force a
        rebuild, the stamp must be deleted. This function will delete the
        specified stamps to force a rebuild.
        """
        # We are only interested in components that create a "stamp" in the
        # "stamps" directory. The "stamps" directory is stripped from the
        # component
        stamps = [component[7:] for component in self._make('list').strip().split(' ')
                  if component.startswith('stamps/')]

        # The user can also specify "libs2e" rather than the complete
        # "libs2e-{release,debug}-make" stamp
        stamp_prefixes = {component.split('-')[0] for component in stamps}

        stamps_to_delete = []
        for component in components:
            # Check if the specified component is valid "as is"
            if component in stamps:
                stamps_to_delete.append(self.env_path('build', 'stamps', component))
                continue

            # Check if the user has specified a valid component prefix
            # TODO: This will delete both the debug and release stamps (if they exist)
            if component in stamp_prefixes:
                stamps_to_delete.extend(glob.glob(self.env_path('build', 'stamps', '%s-*' % component)))
                continue

            # If we've made it this far, the component is not valid
            raise CommandError('Component %s is not valid. Valid components '
                               'are: %s' % (component, ', '.join(stamp_prefixes)))

        # Delete the stamps, ignoring any stamps that do not exist
        for stamp_to_delete in stamps_to_delete:
            try:
                os.remove(stamp_to_delete)
                logger.info('Deleted %s to force a rebuild', stamp_to_delete)
            except OSError:
                pass

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


import json
import logging
import os
import shutil

import sh
from sh import ErrorReturnCode

try:
    from tempfile import TemporaryDirectory
except ImportError:
    from s2e_env.utils.tempdir import TemporaryDirectory

from s2e_env.command import CommandError
from .basic_block import BasicBlockCoverage, BasicBlockDecoder


logger = logging.getLogger('basicblock')


def _get_ida_path(ida_dir, arch):
    """
    Returns the path to the required IDA Pro executable.

    IDA Pro 7 renamed ``idal`` (on Linux) to ``idat`` on (on all platforms).
    See https://www.hex-rays.com/products/ida/7.0/docs/api70_porting_guide.shtml
    for details.

    If we are analysing a 64-bit binary, then we must also use the 64-bit
    version of IDA Pro.

    Args:
        ida_dir: The path to the IDA Pro directory (as specified in the S2E
                 environment's config file).
        arch: The target binary's architecture (as specified in the project
              description file).

    Returns:
        The path to the IDA Pro executable to use.
    """
    for ida_bin in ('idat', 'idal'):
        ida_path = os.path.join(ida_dir, ida_bin)

        if arch == 'x86_64':
            ida_path = '%s64' % ida_path
        elif arch != 'i386':
            raise CommandError('Invalid project architecture `%s` - unable to '
                               'determine the IDA Pro version' % arch)

        if os.path.isfile(ida_path):
            return ida_path

    raise CommandError('IDA Pro not found at %s' % ida_dir)


class IDABasicBlockCoverage(BasicBlockCoverage):
    """
    Generate a basic block coverage report using IDA Pro as the disassembler
    backend.
    """

    def __init__(self):
        super(IDABasicBlockCoverage, self).__init__()

        self._ida_path = None

    def _initialize_disassembler(self):
        """
        Initialize the IDA Pro disassembler.

        Determine which version of IDA to use based on the project's
        architecture (32 or 64 bit).

        Sets the ``_ida_path`` attribute or raises an exception if IDA Pro
        cannot be found.
        """
        ida_dir = self.config.get('ida', {}).get('dir')
        if not ida_dir:
            raise CommandError('No path to IDA has been given in s2e.yaml. '
                               'Please add the following to your s2e.yaml '
                               'config to use this disassembler backend:\n\n'
                               'ida:\n'
                               '\tdir: /path/to/ida')

        self._ida_path = _get_ida_path(ida_dir, self._project_desc['target_arch'])

    def _get_disassembly_info(self, module_path):
        """
        Extract disassembly information from the given module using S2E's IDA
        Pro script.

        This extraction is done within a temporary directory so that we don't
        pollute the file system with temporary idbs and other such things.
        """
        logger.info('Generating disassembly information from IDA Pro for %s',
                    module_path)

        try:
            with TemporaryDirectory() as temp_dir:
                # Copy the binary to the temporary directory. Because projects
                # are created with a symlink to the given module, IDA Pro
                # will generate the idb and disas files in the symlinked
                # module's directory. This is not what we want
                module_name = os.path.basename(module_path)

                temp_module_path = os.path.join(temp_dir, module_name)
                shutil.copyfile(module_path, temp_module_path)

                # Run the IDA Pro extractBasicBlocks script
                env_vars = os.environ.copy()
                env_vars['TVHEADLESS'] = '1'
                # This is required if s2e-env runs inside screen
                env_vars['TERM'] = 'xterm'

                ida = sh.Command(self._ida_path)
                ida('-A', '-B',
                    '-S%s' % self.install_path('bin', 'extractBasicBlocks.py'),
                    temp_module_path, _out=os.devnull, _tty_out=False,
                    _cwd=temp_dir, _env=env_vars)

                # Check that the basic block list file was correctly generated
                disas_file = os.path.join(temp_dir, '%s.disas' % module_name)
                if not os.path.isfile(disas_file):
                    raise CommandError('Failed to generate disas file for '
                                       '%s' % module_name)

                logger.info('Disassembly successful')
                # Parse the basic block list file
                with open(disas_file, 'r') as f:
                    return json.load(f, cls=BasicBlockDecoder)
        except ErrorReturnCode as e:
            raise CommandError(e)

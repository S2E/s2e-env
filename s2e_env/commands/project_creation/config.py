"""
Copyright (c) 2017 Cyberhaven

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

import logging
from s2e_env.command import CommandError
from s2e_env.utils.elf import ELFAnalysis

logger = logging.getLogger('new_project')


class ProjectConfiguration(object):
    def __init__(self):
        pass

    def validate_binary(self, target_arch, os_desc):
        if target_arch == 'x86_64' and os_desc['arch'] != 'x86_64':
            raise CommandError('Binary is x86_64 while VM image is %s. Please '
                               'choose another image.' % os_desc['arch'])

    def validate_configuration(self, config):
        pass

    def analyze(self, config):
        pass


class WindowsProjectConfiguration(ProjectConfiguration):
    BOOTSTRAP_TEMPLATE = 'bootstrap.windows.sh'
    LUA_TEMPLATE = 's2e-config.windows.lua'
    PROJECT_TYPE = 'windows'

    def __init__(self):
        super(WindowsProjectConfiguration, self).__init__()

    def validate_binary(self, target_arch, os_desc):
        if 'pe' not in os_desc['binary_formats']:
            raise CommandError('Please use a Windows image for this binary')

    def validate_configuration(self, config):
        pass


class LinuxProjectConfiguration(ProjectConfiguration):
    BOOTSTRAP_TEMPLATE = 'bootstrap.linux.sh'
    LUA_TEMPLATE = 's2e-config.linux.lua'
    PROJECT_TYPE = 'linux'

    def __init__(self):
        super(LinuxProjectConfiguration, self).__init__()

    def validate_binary(self, target_arch, os_desc):
        if 'elf' not in os_desc['binary_formats']:
            raise CommandError('Please use a Linux image for this binary')

    def analyze(self, config):
        with ELFAnalysis(config['target_path']) as elf:
            config['dynamically_linked'] = elf.is_dynamically_linked()
            config['modelled_functions'] = elf.get_modelled_functions()


class CGCProjectConfiguration(ProjectConfiguration):
    BOOTSTRAP_TEMPLATE = 'bootstrap.cgc.sh'
    LUA_TEMPLATE = 's2e-config.cgc.lua'
    PROJECT_TYPE = 'cgc'

    def __init__(self):
        super(CGCProjectConfiguration, self).__init__()

    def validate_binary(self, target_arch, os_desc):
        if 'decree' not in os_desc['binary_formats']:
            raise CommandError('Please use a CGC image for this binary')

    def validate_configuration(self, config):
        args = config.get('target_args', [])
        if args:
            raise CommandError('Command line arguments for Decree binaries '
                               'not supported')

        use_seeds = config.get('use_seeds', False)
        if not use_seeds:
            logger.warn('CGC requires seeds, forcing seed option on')
            config['use_seeds'] = True

        use_recipes = config.get('use_recipes', False)
        if not use_recipes:
            logger.warn('CGC requires recipes, forcing recipe option on')
            config['use_recipes'] = True

        # CGC binaries do not have input files
        config['warn_input_file'] = False
        config['warn_seeds'] = False

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
from s2e_env.analysis.elf import ELFAnalysis
from s2e_env.analysis.pe import PEAnalysis


logger = logging.getLogger('new_project')


def is_valid_arch(target_arch, os_desc):
    """
    Check that the image's architecture is consistent with the target binary.
    """
    return not (target_arch == 'x86_64' and os_desc['arch'] != 'x86_64')


class ProjectConfiguration(object):
    def is_valid_binary(self, target_arch, target_path, os_desc):
        """
        Validate a binary against a particular image description.

        This validation may vary depending on the binary and image type.
        Returns ``True`` if the binary is valid and ``False`` otherwise.
        """
        pass

    def validate_configuration(self, config):
        """
        Validate a project's configuration options.

        This method may modify values in the ``config`` dictionary. If an
        invalid configuration is found, a ``CommandError` should be thrown.
        """
        pass

    def analyze(self, config):
        """
        Perform static analysis on the target binary.

        The results of this analysis can be used to add and/or modify values in
        the ``config`` dictionary.
        """
        pass


class WindowsProjectConfiguration(ProjectConfiguration):
    BOOTSTRAP_TEMPLATE = 'bootstrap.windows.sh'
    LUA_TEMPLATE = 's2e-config.windows.lua'
    PROJECT_TYPE = 'windows'

    def is_valid_binary(self, target_arch, target_path, os_desc):
        return is_valid_arch(target_arch, os_desc) and 'pe' in os_desc['binary_formats']

    def validate_configuration(self, config):
        # Make all module names lower-case (in line with the WindowsMonitor plugin)
        config['modules'] = [(mod.lower(), kernel_mode) for mod, kernel_mode in config.get('modules', [])]


class WindowsDLLProjectConfiguration(WindowsProjectConfiguration):
    BOOTSTRAP_TEMPLATE = 'bootstrap.windows_dll.sh'
    LUA_TEMPLATE = 's2e-config.windows.lua'
    PROJECT_TYPE = 'windows'

    def is_valid_binary(self, target_arch, target_path, os_desc):
        if not target_path.endswith('.dll'):
            raise CommandError('Invalid DLL name - requires .dll extension')

        return super(WindowsDLLProjectConfiguration, self).is_valid_binary(target_arch, target_path, os_desc)

    def validate_configuration(self, config):
        super(WindowsDLLProjectConfiguration, self).validate_configuration(config)

        if config.get('use_seeds', False):
            logger.warn('Seeds have been enabled, however they are not supported for DLLs. This flag will be ignored')
            config['use_seeds'] = False

        if not config.get('target_args', []):
            logger.warn('No DLL entry point provided - defaulting to ``DllEntryPoint``')
            config['target_args'] = ['DllEntryPoint']

    def analyze(self, config):
        with PEAnalysis(config['target_path']) as pe:
            config['dll_exports'] = pe.get_exports()


class WindowsDriverProjectConfiguration(WindowsProjectConfiguration):
    BOOTSTRAP_TEMPLATE = 'bootstrap.windows_driver.sh'
    LUA_TEMPLATE = 's2e-config.windows.lua'
    PROJECT_TYPE = 'windows'

    def validate_configuration(self, config):
        super(WindowsDriverProjectConfiguration, self).validate_configuration(config)

        if config.get('use_seeds', False):
            logger.warn('Seeds have been enabled, however they are not supported for device drivers.'
                        ' This flag will be ignored')
            config['use_seeds'] = False

        # Fault injection works best with DFS (we want exhaustive exploration)
        if config.get('use_cupa', False):
            config['use_cupa'] = False

        # Device drivers do not have input files
        config['warn_input_file'] = False
        config['warn_seeds'] = False

        # All we support for now
        config['use_fault_injection'] = True


class LinuxProjectConfiguration(ProjectConfiguration):
    BOOTSTRAP_TEMPLATE = 'bootstrap.linux.sh'
    LUA_TEMPLATE = 's2e-config.linux.lua'
    PROJECT_TYPE = 'linux'

    def is_valid_binary(self, target_arch, target_path, os_desc):
        return is_valid_arch(target_arch, os_desc) and 'elf' in os_desc['binary_formats']

    def analyze(self, config):
        with ELFAnalysis(config['target_path']) as elf:
            config['dynamically_linked'] = elf.is_dynamically_linked()
            config['modelled_functions'] = elf.get_modelled_functions()


class CGCProjectConfiguration(ProjectConfiguration):
    BOOTSTRAP_TEMPLATE = 'bootstrap.cgc.sh'
    LUA_TEMPLATE = 's2e-config.cgc.lua'
    PROJECT_TYPE = 'cgc'

    def is_valid_binary(self, target_arch, target_path, os_desc):
        return is_valid_arch(target_arch, os_desc) and 'decree' in os_desc['binary_formats']

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

        # CGC has its own test case generation system
        config['use_test_case_generator'] = False

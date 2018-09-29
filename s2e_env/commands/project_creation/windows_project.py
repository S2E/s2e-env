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

from s2e_env.analysis.pe import PEAnalysis
from s2e_env.command import CommandError
from . import is_valid_arch, Project


logger = logging.getLogger('new_project')


class WindowsProject(Project):
    def __init__(self, bootstrap_template='bootstrap.windows.sh'):
        super(WindowsProject, self).__init__('windows', bootstrap_template,
                                             's2e-config.windows.lua')

    def _is_image_valid(self, target_arch, target_path, os_desc):
        return is_valid_arch(target_arch, os_desc) and 'pe' in os_desc['binary_formats']

    def _validate_config(self, config):
        # Make all module names lower-case (in line with the WindowsMonitor plugin)
        config['modules'] = [(mod.lower(), kernel_mode) for mod, kernel_mode in config.get('modules', [])]


class WindowsDLLProject(WindowsProject):
    def __init__(self):
        super(WindowsDLLProject, self).__init__('bootstrap.windows_dll.sh')

    def _is_image_valid(self, target_arch, target_path, os_desc):
        if not target_path.endswith('.dll'):
            raise CommandError('Invalid DLL name - requires .dll extension')

        return super(WindowsDLLProject, self)._is_image_valid(target_arch, target_path, os_desc)

    def _validate_config(self, config):
        super(WindowsDLLProject, self)._validate_config(config)

        # Not supported for DLLs
        config['processes'] = []

        if config.get('use_seeds', False):
            logger.warn('Seeds have been enabled, however they are not supported for DLLs. This flag will be ignored')
            config['use_seeds'] = False

        if not config.get('target_args', []):
            logger.warn('No DLL entry point provided - defaulting to ``DllEntryPoint``')
            config['target_args'] = ['DllEntryPoint']

    def _analyze_target(self, target_path, config):
        with PEAnalysis(target_path) as pe:
            config['dll_exports'] = pe.get_exports()


class WindowsDriverProject(WindowsProject):
    def __init__(self):
        super(WindowsDriverProject, self).__init__('bootstrap.windows_driver.sh')

    def _is_image_valid(self, target_arch, target_path, os_desc):
        # Windows drivers must match the OS's bit-ness
        return os_desc['name'] == 'windows' and os_desc['arch'] == target_arch

    def _validate_config(self, config):
        super(WindowsDriverProject, self)._validate_config(config)

        # Not supported for drivers
        config['processes'] = []

        # All we support for now
        config['use_fault_injection'] = True

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


from s2e_env.analysis.elf import ELFAnalysis

from .base_project import is_valid_arch, BaseProject


class LinuxProject(BaseProject):
    def __init__(self):
        super(LinuxProject, self).__init__('bootstrap.linux.sh',
                                           's2e-config.linux.lua')

    def _is_valid_image(self, target, os_desc):
        return is_valid_arch(target.arch, os_desc) and 'elf' in os_desc['binary_formats']

    def _analyze_target(self, target, config):
        with ELFAnalysis(target.path) as elf:
            config['dynamically_linked'] = elf.is_dynamically_linked()
            config['modelled_functions'] = elf.get_modelled_functions()

    def _finalize_config(self, config):
        config['project_type'] = 'linux'

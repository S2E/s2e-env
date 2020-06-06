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

from .base_project import is_valid_arch, BaseProject


logger = logging.getLogger('new_project')


class CGCProject(BaseProject):
    def __init__(self):
        super(CGCProject, self).__init__('bootstrap.cgc.sh',
                                         's2e-config.cgc.lua')

    def _is_valid_image(self, target, os_desc):
        return is_valid_arch(target.arch, os_desc) and 'decree' in os_desc['binary_formats']

    def _finalize_config(self, config):
        config['project_type'] = 'cgc'

        args = config.get('target').args.raw_args
        if args:
            raise CommandError('Command line arguments for Decree binaries '
                               'not supported')

        single_path = config.get('single_path', False)
        if single_path:
            logger.warning('CGC requires multi-path mode, forcing single path option off')
            config['single_path'] = False

        use_seeds = config.get('use_seeds', False)
        if not use_seeds:
            logger.warning('CGC requires seeds, forcing seed option on')
            config['use_seeds'] = True

        use_recipes = config.get('use_recipes', False)
        if not use_recipes:
            logger.warning('CGC requires recipes, forcing recipe option on')
            config['use_recipes'] = True

        enable_pov_generation = config.get('enable_pov_generation', False)
        if not enable_pov_generation:
            logger.warning('CGC required PoV generation, forcing POV generation option on')
            config['enable_pov_generation'] = True

        # CGC binaries do not have input files
        config['warn_input_file'] = False
        config['warn_seeds'] = False

        # CGC has its own test case generation system
        config['use_test_case_generator'] = False

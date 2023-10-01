"""
Copyright (c) 2023 Vitaly Chipounov

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

from .base_project import BaseProject


logger = logging.getLogger('new_project')


class BIOSProject(BaseProject):
    supported_tools = []
    image = {
        "image_group": "bios",
        "memory": "4M",
        "name": "bios",
        "os": None,
        "qemu_build": "x86_64",
        "qemu_extra_flags": "-net none -net nic,model=e1000 ",
        "snapshot": None,
        "version": 3
    }

    def __init__(self):
        super().__init__(None, 's2e-config.bios.lua', BIOSProject.image)

    def _is_valid_image(self, target, os_desc):
        # Any image is ok for BIOS, they will just be ignored.
        return True

    def _finalize_config(self, config):
        config['project_type'] = 'bios'

        args = config.get('target').args.raw_args
        if args:
            raise CommandError('Command line arguments for BIOS binaries '
                               'not supported')

        config['bios'] = config['target'].path

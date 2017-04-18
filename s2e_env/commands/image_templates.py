"""
MIT License

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


from __future__ import print_function

import glob
import json
import os

from s2e_env import CONSTANTS
from s2e_env.command import EnvCommand


def image_templates(dirs):
    templates = []
    get_filename = lambda f: os.path.splitext(os.path.basename(f))[0]

    for src_dir in dirs:
        for template_path in glob.glob(os.path.join(src_dir, '*.json')):
            with open(template_path, 'r') as f:
                template_json = json.load(f)

                templates.append((get_filename(template_path),
                                  template_json.get('description', '')))

    return templates


class Command(EnvCommand):
    """
    Lists the image templates that are available to build.
    """

    help = 'Lists the image templates that are available to build'

    def handle(self, **options):
        img_src_dirs = [self.env_path('source', repo) for repo
                        in CONSTANTS['repos']['images'].values()]
        templates = image_templates(img_src_dirs)

        if not templates:
            print('No images available to build')
        else:
            print('Images available to build:')
            for template, desc in templates:
                print(' * %s - %s' % (template, desc))
            print('\nRun ``s2e image_build <template>`` to build an image. '
                  'Note that you must run ``s2e build`` **before** building '
                  'an image')

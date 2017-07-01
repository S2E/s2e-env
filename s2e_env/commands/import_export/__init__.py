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


import os

from s2e_env import CONSTANTS
from s2e_env.command import CommandError


S2E_ENV_PLACEHOLDER = '<S2E_ENV_PATH>'


def copy_and_rewrite_files(input_dir, output_dir, to_replace, replace_with):
    """
    Copy files from ``input_dir`` to ``output_dir`` and replace all occurances
    of ``to_replace`` with ``replace_with``.
    """
    for file_ in CONSTANTS['exported_files']:
        in_file_path = os.path.join(input_dir, file_)
        out_file_path = os.path.join(output_dir, file_)

        if not os.path.isfile(in_file_path):
            raise CommandError('%s does not exist' % file_)

        # We need to do this to correctly handle in_file_path == out_file_path
        contents = ''
        with open(in_file_path, 'r') as f:
            contents = f.read()
        with open(out_file_path, 'w') as f:
            f.write(contents.replace(to_replace, replace_with))

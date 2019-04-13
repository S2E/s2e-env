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


import logging
import os

from s2e_env import CONSTANTS
from s2e_env.command import CommandError


logger = logging.getLogger('import_export')

S2E_ENV_PLACEHOLDER = '<S2E_ENV_PATH>'


def rewrite_files(dir_, files_to_rewrite, to_replace, replace_with):
    """
    Rewrites the files in ``dir__ such that any file listed in
    ``files_to_rewrite`` has all occurrences of ``to_replace`` replaced by
    ``replace_with``.
    """
    for name in os.listdir(dir_):
        path = os.path.join(dir_, name)

        if not os.path.isfile(path):
            continue

        if not name in files_to_rewrite:
            continue

        logger.info('Rewriting %s', name)

        with open(path, 'r+') as f:
            contents = f.read()
            f.seek(0)
            f.write(contents.replace(to_replace, replace_with))
            f.truncate()

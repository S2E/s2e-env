"""
Copyright (c) 2013-2014 Dependable Systems Laboratory, EPFL
Copyright (c) 2018 Cyberhaven

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
import logging
import sys

# TODO: inf parser shall not depend on anything in s2e-env
# Eventually, we'll publish it as a standalone Python package
from ..utils import log

from .driver import Driver

logger = logging.getLogger('infparser')


def get_inf_files(directory):
    ret = set()

    for r, _, f in os.walk(directory):
        for files in f:
            if files.endswith('.inf'):
                inf = os.path.join(r, files)
                ret.add(inf)

    return ret


def main():
    log.configure_logging()

    argv = sys.argv[1:]
    if len(argv) < 1:
        logger.error('Usage: parseinf [directory|inffile]')
        return

    path = argv[0]
    if not os.path.exists(path):
        logger.error('%s does not exist', path)

    files = set()
    if os.path.isfile(path):
        files.add(path)
    else:
        files = get_inf_files(path)

    for inf_file in files:
        driver = Driver(inf_file)
        driver.analyze()
        driver_files = driver.get_files()
        logger.info('  Driver files:')
        for f in driver_files:
            logger.info('    %s', f)


if __name__ == '__main__':
    main()

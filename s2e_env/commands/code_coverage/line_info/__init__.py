"""
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

import logging

from s2e_env.commands.code_coverage.line_info import dwarf
from s2e_env.commands.code_coverage.line_info import jsoninfo

from s2e_env.command import CommandError

logger = logging.getLogger('line_info')


def get_file_line_coverage(target_path, addr_counts):
    """
        Map addresses to line numbers in the source code file.

        Args:
            target_path: Path to the analysis target.
            addr_counts: A dictionary mapping instruction addresses executed by S2E
                         (and recorded by the ``TranslationBlockCoverage`` plugin)
                         to the number of times they were executed.

        Returns:
            A dictionary that maps source code files to line numbers and the number
            of times each line was executed.

            E.g.:
                ```
                {
                    'path/to/source': {
                                          1: 2, # Line 1 was executed twice
                                          2: 5, # Line 2 was executed five times
                                          ...
                                      },
                    ...
                }
                ```
    """

    try:
        return dwarf.get_file_line_coverage(target_path, addr_counts)
    except Exception as e:
        logger.error('Could not read DWARF information from %s: %s', target_path, e)

    try:
        return jsoninfo.get_file_line_coverage(target_path, addr_counts)
    except Exception as e:
        logger.error('Could not get json line information from %s: %s\n'
                     'If you try to get coverage for a Windows binary that has a PDB file,\n'
                     'please use pdbparser.exe to get the json line information.', target_path, e)

    raise CommandError('No usable line information available for %s' % target_path)

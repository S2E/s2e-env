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

import json
import logging

logger = logging.getLogger('jsoninfo')


def _parse_info(lines, addr_counts):
    """
    The line information must have the following format:

    {
        "path/to/file1": [
           [line, address], [line, address], ...
        ],
        "path/to/file2": [
           ...
        ]
    }

    This is typically used to get coverage for Windows binaries.
    The pdbparser.exe tool takes a PDB and EXE file, and outputs
    data in the above format.
    """
    file_line_info = {}

    for filepath, line_info in lines.iteritems():
        current_file = {}

        if filepath in file_line_info:
            current_file = file_line_info[filepath]
        else:
            file_line_info[filepath] = current_file

        for line in line_info:
            line_number = line[0]
            address = line[1]

            if line_number not in current_file:
                current_file[line_number] = 0

            if address in addr_counts:
                current_file[line_number] += addr_counts[address]

    return file_line_info


def get_file_line_coverage(target_path, addr_counts):
    target_path = '%s.lines' % target_path

    with open(target_path, 'r') as f:
        logger.info('Using %s as source of line information', target_path)
        lines = json.loads(f.read())
        return _parse_info(lines, addr_counts)

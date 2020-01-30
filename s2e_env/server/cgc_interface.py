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
import os

from .collector_threads import CollectorThreads
from . import coverage


logger = logging.getLogger(__name__)


def translate_paths(analysis, data):
    """
    Converts relative paths returned by S2E into absolute paths
    relative to checkers output folder.
    """

    s2e_output_path = analysis['output_path']
    keys = [
        'constraints_filename', 'xml_testcase_filename',
        'c_testcase_filename', 'coverage_filename',
        'tbcoverage_filename', 'callsites_filename'
    ]

    for k in keys:
        original = data.get(k, None)
        if original is None:
            continue

        data[k] = os.path.join(s2e_output_path, original)


class CGCInterfacePlugin:
    crash_count = 0
    pov1_count = 0
    pov2_count = 0

    @staticmethod
    def handle_testcase(analysis, data):
        testcase_type = data.get('testcase_type', None)

        if testcase_type == 'pov':
            pov_type = data.get('pov_type', None)
            if pov_type == 1:
                CGCInterfacePlugin.pov1_count += 1
            elif pov_type == 2:
                CGCInterfacePlugin.pov2_count += 1
        elif testcase_type == 'crash':
            CGCInterfacePlugin.crash_count += 1

        s2e_coverage_file = data.get('coverage_filename', None)
        if s2e_coverage_file is not None:
            CollectorThreads.coverage.queue_coverage(
                analysis, s2e_coverage_file, coverage.BB_COVERAGE, None
            )

        s2e_tbcoverage_file = data.get('tbcoverage_filename', None)
        if s2e_tbcoverage_file is not None:
            CollectorThreads.coverage.queue_coverage(
                analysis, s2e_tbcoverage_file, coverage.TB_COVERAGE, None
            )

    @staticmethod
    def handle_stats(analysis, data):
        CollectorThreads.stats.queue_stats(analysis, data)

    @staticmethod
    def process(data, analysis):
        data_type = data.get('type', None)

        if data_type not in ('db_error', 'testcase', 'recipe', 'stats'):
            return

        if data_type == 'db_error':
            return

        translate_paths(analysis, data)

        if data_type == 'stats':
            CGCInterfacePlugin.handle_stats(analysis, data)
            return

        logger.info('Processing request %s', data)

        if data_type == 'testcase':
            CGCInterfacePlugin.handle_testcase(analysis, data)
            return

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


import json
import logging
import os

from .threads import terminating
from .queueprocessor import QueueProcessor


logger = logging.getLogger(__name__)

BB_COVERAGE = 0
TB_COVERAGE = 1


class Coverage(QueueProcessor):
    def __init__(self):
        QueueProcessor.__init__(self)
        # Split Bb and Tb coverage for stats purposes.
        # The DB stores mixed info.
        self._bb_coverage = {}
        self._tb_coverage = {}
        self._static_info = {}
        self._summary_updated = False
        self._summary = {}

    def update_summary(self):

        bb_summary = {}
        bb_aggregate = 0
        bb_static_aggregate = 0
        for module, coverage in self._bb_coverage.items():
            l = len(coverage)
            bb_summary[module] = l
            bb_aggregate += l
            bb_static_aggregate += self._static_info[module]['static_bbs']

        tb_aggregate = 0
        for module, coverage in self._tb_coverage.items():
            l = len(coverage)
            tb_aggregate += l

        coverage = {
            'breakdown': bb_summary,
            'covered_tbs_total': tb_aggregate,
            'covered_bbs_total': bb_aggregate,
            'available_bbs_total': bb_static_aggregate
        }

        logger.info('Updating coverage summary %s', coverage)

        self._summary = coverage
        self._summary_updated = True

    def compute_bb_diff(self, data, is_tb=False):
        result = {}

        if is_tb:
            actual_cov = self._tb_coverage
        else:
            actual_cov = self._bb_coverage

        for module, coverage in data.items():
            if module not in actual_cov:
                result[module] = coverage
                actual_cov[module] = set()

            data_set = set()
            if is_tb:
                cdata = coverage
            else:
                cdata = coverage['covered_blocks']

            for bb in cdata:
                # Both BB and TB coverage data items begin with start_pc and end_pc
                t = (bb[0], bb[1])
                data_set.add(t)

            result[module] = data_set.difference(actual_cov[module])

        return result

    def is_covered(self, module, bb):
        bbs = self._bb_coverage.get(module, {})
        tbs = self._tb_coverage.get(module, {})

        return bb in bbs or bb in tbs

    def process_coverage(self, _, coverage_file, coverage_type):
        with open(coverage_file) as fp:
            data = json.load(fp)

        os.remove(coverage_file)

        diff = self.compute_bb_diff(data, coverage_type == TB_COVERAGE)

        logger.info('Processing coverage data diff: %s', diff)
        for module, coverage in diff.items():
            logger.info('module: %s coverage: %s ', module, coverage)

            for bb in coverage:
                # In principle, we could have a diff over the union of bbs
                # and tbs, but it's just simpler to filter out here.
                if self.is_covered(module, bb):
                    continue

                logger.info('Found new bb: %s %x:%x', module, bb[0], bb[1])

                self._summary_updated = False

            if coverage_type == TB_COVERAGE:
                self._tb_coverage[module] = self._tb_coverage[module].union(coverage)
            else:
                self._bb_coverage[module] = self._bb_coverage[module].union(coverage)
                self._static_info[module] = {
                    'static_bbs': data[module]['static_bbs']
                }

        if not self._summary_updated:
            self.update_summary()

    def run(self):
        logger.info('Starting coverage thread')

        while not terminating():

            try:
                # Need timeout to avoid getting stuck on termination
                item = self._queue.get(True, 2)
            except Exception:
                continue

            (analysis, coverage_file, coverage_type, cb) = item

            try:
                self.process_coverage(analysis, coverage_file, coverage_type)

                if cb is not None:
                    cb(analysis, item)
            except Exception as e:
                # Log the errors, don't crash the thread
                logger.error(e, exc_info=True)

        logger.info('Terminating coverage thread')

    def queue_coverage(self, analysis, coverage_file, coverage_type, cb):
        logger.info('Queuing coverage file %s', coverage_file)
        item = (analysis, coverage_file, coverage_type, cb)
        self._queue.put(item)

    @property
    def tb_coverage(self):
        return self._tb_coverage

    @property
    def summary(self):
        return self._summary

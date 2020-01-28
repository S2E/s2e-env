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
from threading import Thread
from queue import Queue
from .threads import terminating


logger = logging.getLogger(__name__)


class CGCStats(Thread):
    def __init__(self):
        Thread.__init__(self)
        self._queue = Queue()
        self._stats = {}
        self._global_stats = {}

    def process_stats(self, _, data):
        # Update per-module stats
        stats = data.get('stats', {})
        for module, mdata in stats.items():
            upd = self._stats.get(module, {})
            upd['called_random'] = upd.get('called_random', False) or mdata.get('called_random', False)
            upd['random_branches_pc'] = list(
                set(upd.get('random_branches_pc', [])).union(mdata.get('random_branches_pc', [])))
            self._stats[module] = upd

        # Update global stats
        gs = data.get('global_stats', {})

        self._global_stats['states'] = self._global_stats.get('states', 0) + \
            gs.get('states_delta', 0)

        max_stats = [
            'state_highest_id',
            'state_max_completed_depth',
            'state_max_depth',
            'seeds_used',
            'recipe_count',
            'invalid_recipe_count',
            'cfg_bb_count',
            'model_count',
            'instance_max_count',
            'instance_current_count',
        ]

        for s in max_stats:
            self._global_stats[s] = max(self._global_stats.get(s, 0),
                                        gs.get(s, 0))

        aggregated_stats = [
            'state_completed_count',
            'seeds_completed',
            'recipe_invalid_count',
            'recipe_failed_tries',
            'recipe_successful_tries',
            'recipe_count',
            'segfault_count',
        ]

        for s in aggregated_stats:
            self._global_stats[s] = self._global_stats.get(s, 0) + gs.get(s, 0)

    def run(self):
        logger.info('Starting stats collection thread')

        while not terminating():
            try:
                # Need timeout to avoid getting stuck on termination
                analysis, data = self._queue.get(True, 2)
            except Exception:
                continue

            try:
                self.process_stats(analysis, data)
            except Exception as e:
                # Log the errors, don't crash the thread
                logger.error(e, exc_info=True)

        logger.info('Terminating stats collection thread')

    def queue_stats(self, analysis, data):
        data = (analysis, data)
        self._queue.put(data)

    @property
    def global_stats(self):
        return self._global_stats

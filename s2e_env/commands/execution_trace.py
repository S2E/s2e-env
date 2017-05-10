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


import json
import logging
import os

from s2e_env.command import ProjectCommand, CommandError
from s2e_env.execution_trace import parse as parse_execution_trace


logger = logging.getLogger('execution_trace')


def _make_json_entry(header, item):
    """
    Combine a trace entry header and item into a single entry. Return this
    entry as a ``dict``.

    Some things to note:
        * The header's ``size`` field is removed - it is not required in the
          JSON
        * Enums are replaced by their numerical value (so that they can be
          written to JSON)
    """
    from enum import Enum

    header_dict = header.as_dict()

    del header_dict['size']

    entry = header_dict.copy()
    entry.update(item.as_dict())

    for key, value in entry.items():
        if isinstance(value, Enum):
            entry[key] = value.value

    return entry


class Command(ProjectCommand):
    """
    Parses an execution trace into JSON.
    """

    help = 'Parse an S2E execution trace into JSON.'

    def handle(self, *args, **options):
        # Get the ExecutionTrace.dat file from s2e-last
        execution_trace_path = self.project_path('s2e-last', 'ExecutionTracer.dat')
        if not os.path.isfile(execution_trace_path):
            raise CommandError('No \'ExecutionTrace.dat\' file found in s2e-last. '
                               'Did you enable any trace plugins in s2e-config.lua?')

        # Parse ExecutionTrace.dat and collect the results.
        with open(execution_trace_path, 'r') as trace_file:
            results = parse_execution_trace(trace_file)

        json_trace_file = self._save_execution_trace(results)

        return 'Execution trace saved to %s' % json_trace_file

    def _save_execution_trace(self, trace):
        """
        Write the execution trace information to a JSON file.

        Returns the path to the JSON file.
        """
        trace_file = self.project_path('s2e-last', 'execution_trace.json')

        logger.info('Saving execution trace to %s', trace_file)

        trace_json = [_make_json_entry(header, item) for header, item in trace]

        with open(trace_file, 'w') as f:
            json.dump(trace_json, f)

        return trace_file

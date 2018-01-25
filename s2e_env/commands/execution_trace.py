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


import binascii
import json
import logging

from enum import Enum

from s2e_env.command import ProjectCommand, CommandError
from s2e_env.execution_trace import parse as parse_execution_tree, trace_entries
from s2e_env.execution_trace.trace_entries import TraceEntryType


logger = logging.getLogger('execution_trace')


def _make_json_trace(execution_trace):
    """
    Make an execution trace (consisting of ``TraceEntry`` objects)
    JSON-serializable.
    """
    return [_make_json_entry(header, item) for header, item in execution_trace]


def _make_json_entry(header, item):
    """
    Combine a trace entry header and item into a single JSON-serializable
    entry. Return this entry as a ``dict``.

    Some things to note:
        * The header's ``size`` field is removed - it is not required in the
          JSON
        * Enums are replaced by their numerical value (so that they can be
          written to JSON)
    """

    # If the entry is a fork, then we have to make the child traces
    # JSON-serializable as well
    if header.type == TraceEntryType.TRACE_FORK:
        children = {state_id: _make_json_trace(trace) for state_id, trace in item.children.items()}
        item = trace_entries.TraceFork(item.pc, children)
    # If the entry is a test case, then we have to "hexlify" the data so that
    # it can be stored in the JSON file
    elif header.type == TraceEntryType.TRACE_TESTCASE:
        data = binascii.hexlify(item.data)
        item = trace_entries.TraceTestCase(item.name, data)

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

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('-p', '--path-id', action='append', type=int,
                            dest='path_ids',
                            help='Path IDs to include in the trace. This '
                                 'option can be used multiple times to trace '
                                 'multiple path IDs')

    def handle(self, *args, **options):
        # Parse the ExecutionTracer.dat file(s) and generate an execution tree
        # for the given path IDs
        results_dir = self.project_path('s2e-last')
        execution_tree = parse_execution_tree(results_dir, path_ids=options['path_ids'])
        if not execution_tree:
            raise CommandError('The execution trace is empty')

        # Convert the tree into a JSON representation
        execution_tree_json = _make_json_trace(execution_tree)

        # Write the execution tree to a JSON file
        json_trace_file = self.project_path('s2e-last', 'execution_trace.json')
        with open(json_trace_file, 'w') as f:
            json.dump(execution_tree_json, f)

        logger.success('Execution trace saved to %s', json_trace_file)

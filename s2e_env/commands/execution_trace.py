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

from protobuf_to_dict import protobuf_to_dict

from s2e_env.command import ProjectCommand, CommandError
from s2e_env.execution_trace import parse as parse_execution_tree
from s2e_env.execution_trace import TraceEntries_pb2, TraceEntryFork


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
    if header.type == TraceEntries_pb2.TRACE_FORK:
        children = {state_id: _make_json_trace(trace) for state_id, trace in item.children.items()}
        item = TraceEntryFork(children)

    header_dict = protobuf_to_dict(header, use_enum_labels=True)

    entry = header_dict.copy()

    if isinstance(item, TraceEntryFork):
        entry.update({'children': item.children})
    else:
        entry.update(protobuf_to_dict(item, use_enum_labels=True))

    return entry


class TraceEncoder(json.JSONEncoder):
    # pylint: disable=method-hidden
    def default(self, o):
        if isinstance(o, bytes):
            chars = []
            for b in o:
                chars.append(b)
            return chars
        return super(TraceEncoder, self).default(o)


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

        parser.add_argument('-pp', '--pretty-print', action='store_true',
                            dest='pretty_print',
                            help='Pretty print the generated json')

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
            if options['pretty_print']:
                json.dump(execution_tree_json, f, indent=4, sort_keys=True, cls=TraceEncoder)
            else:
                print(execution_tree_json)
                json.dump(execution_tree_json, f, cls=TraceEncoder)

        logger.success('Execution trace saved to %s', json_trace_file)

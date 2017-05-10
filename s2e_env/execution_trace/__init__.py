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


import glob
import logging
import operator
import os

from . import trace_entries
from .trace_entries import TraceEntryType, TraceEntryError, TraceItemHeader


logger = logging.getLogger('execution_trace')


# Maps trace entry types to a class
_TRACE_ENTRY_MAP = {
    TraceEntryType.TRACE_MOD_LOAD: trace_entries.TraceModuleLoad,
    TraceEntryType.TRACE_MOD_UNLOAD: trace_entries.TraceModuleUnload,
    TraceEntryType.TRACE_PROC_UNLOAD: trace_entries.TraceProcessUnload,
    TraceEntryType.TRACE_CALL: trace_entries.TraceCall,
    TraceEntryType.TRACE_RET: trace_entries.TraceReturn,
    TraceEntryType.TRACE_TB_START: trace_entries.TraceTranslationBlock,
    TraceEntryType.TRACE_TB_END: trace_entries.TraceTranslationBlock,
    TraceEntryType.TRACE_MODULE_DESC: None,
    TraceEntryType.TRACE_FORK: trace_entries.TraceFork,
    TraceEntryType.TRACE_CACHESIM: trace_entries.TraceCache,
    TraceEntryType.TRACE_TESTCASE: trace_entries.TraceTestCase,
    TraceEntryType.TRACE_BRANCHCOV: trace_entries.TraceBranchCoverage,
    TraceEntryType.TRACE_MEMORY: trace_entries.TraceMemory,
    TraceEntryType.TRACE_PAGEFAULT: trace_entries.TracePageFault,
    TraceEntryType.TRACE_TLBMISS: trace_entries.TraceTLBMiss,
    TraceEntryType.TRACE_ICOUNT: trace_entries.TraceInstructionCount,
    TraceEntryType.TRACE_MEM_CHECKER: trace_entries.TraceMemChecker,
    TraceEntryType.TRACE_EXCEPTION: trace_entries.TraceException,
    TraceEntryType.TRACE_STATE_SWITCH: trace_entries.TraceStateSwitch,
    TraceEntryType.TRACE_TB_START_X64: trace_entries.TraceTranslationBlock64,
    TraceEntryType.TRACE_TB_END_X64: trace_entries.TraceTranslationBlock64,
    TraceEntryType.TRACE_BLOCK: trace_entries.TraceBlock,
}


class ExecutionTraceParser(object):
    """
    Parser for S2E execution trace files.

    The parsing algorithm is described below. Note that "state" and "path" are
    used interchangably (the term "state" is used in the S2E code base, however
    a state is essentially an execution path through a program).

    If S2E is run in multiprocess mode, each process will create and write to
    its own ``ExecutionTracer.dat`` file. So first we parse each
    ``ExecutionTracer.dat`` file individually.

    While parsing we maintain a global (i.e. across all trace files) map of
    state IDs to parent state ID and fork points (the ``_path_info``
    attribute). This map is then used to reconstruct the final execution tree
    once all traces have been parsed.

    Take the following execution tree, where ``Sx`` refers to a state ID with
    ID ``x``:

    .. code-block::

        S0
        |
        S0
        |
        S0
        | \
        S0 S1
        |  |
        S0 S1
        .  | \
        .  S1 S2
        .  |  |
        .  .  .

    After parsing the ``ExecutionTracer.dat`` file(s) the ``_execution_traces``
    map will look as follows:

    .. code-block::

        _execution_traces = {
            0: [S0_0, S0_1, S0_2, S0_3, S0_4, ...],
            1: [S1_0, S1_1, S1_2, ...],
            2: [S2_0, ...],
        }

    We iterate over ``_execution_traces`` from the highest state ID (i.e. the
    state that was forked last) to the lowest (state 0, the initial state).

    For each execution trace, its parent and fork point is looked up in
    ``_path_info``. In this example, S2's parent is S1 and fork point is 1
    (because the fork occurred at index 1 of the S1 execution trace list).
    Because the fork point is at 1, we know that the ``TraceItemEntry`` at
    index 1 is a ``TraceFork`` object. We then take the S2 execution trace list
    and insert it into the ``TraceFork``'s ``children`` attribute.

    Repeating the process for S1, we get parent state S0 and fork point 2
    (because the fork occurred at index 2 of the S0 execution trace list). Once
    again we can insert the S1 list into the ``children`` attribute at this
    fork point.

    Finally, we terminate because S0 has no parent. The entire execution tree
    is now stored in the S0 execution trace list.

    Now assume that the user is only interested in S1. During the initial file
    parsing phase, we can assume that any state > 1 is forked after S1 is
    forked and hence is of no interest. Therefore we do not need to store the
    data associated with these states.

    During the construction of the final tree, we can further discard
    information that is no longer required. For example, after S0 forks S1, we
    are no longer interested in the remainder of S0 (i.e. elements ``[S0_3,
    S0_4, ...]`` in ``_execution_traces[0]``). Likewise if the user is only
    interested in S2, then all of the trace entries that follow S2's fork point
    (i.e. ``[S1_2, ...]``) and S1's fork point (i.e. ``[S0_3, S0_4, ...]``) can
    be discarded.

    Attributes:
        _trace_files: A list of ``ExecutionTracer.dat`` file paths.
        _execution_traces: A dictionary of state IDs to the execution trace (a
                           list of ``(TraceItemHeader, TraceEntry)`` tuples).
        _path_info: A map of state IDs to a tuple containing:
                        1. The parent state's ID
                        2. A "fork point". This is an index into state ID's
                           trace in the ``_execution_traces`` dictionary. This
                           index points to to a ``TraceFork`` object and hence
                           where a fork occurred.
    """

    def __init__(self, trace_files):
        self._trace_files = trace_files
        self._execution_traces = {}
        self._path_info = {}

    def parse(self, path_ids=None):
        """
        Parse the list of trace files and generate a single execution tree
        representing the complete trace.

        The execution tree is a list of ``(TraceItemHeader, TraceEntry)``
        tuples. If the ``TraceEntry`` is a ``TraceFork``, the list splits into
        ``n`` sublists, where ``n`` is the number of child states forked. These
        sublists can be accessed through the ``TraceFork``'s ``children``
        attribute.

        Args:
            path_ids: Optional list of path (state) IDs to include in the
                      execution tree. If no path IDs are given, the complete
                      execution tree is parsed.
        """
        # Parse individual trace files
        for trace_file_path in self._trace_files:
            with open(trace_file_path, 'r') as trace_file:
                logger.debug('Parsing %s', trace_file_path)
                self._parse_trace_file(trace_file, path_ids)

        # Sort the execution trace for each state
        for execution_trace in self._execution_traces.values():
            execution_trace.sort(key=lambda x: x[0].timestamp)

        # If a list of path IDs is given, we will return these states plus
        # their parents.
        #
        # If no path IDs are given, we will return all states.
        if path_ids:
            states_to_return = set(path_ids)
            for state_id in path_ids:
                parent_states = self._get_parent_states(state_id)
                states_to_return.update(parent_states)

            # Exclude the initial state, state 0, because that will always be
            # the root of the execution tree
            states_to_return.discard(0)
        else:
            states_to_return = self._path_info.keys()

        # Reconstruct the execution tree for the given state IDs
        for state_id in sorted(states_to_return, reverse=True):
            parent_state_id, fork_point = self._path_info[state_id]
            parent_execution_trace = self._execution_traces[parent_state_id]
            _, trace_fork = parent_execution_trace[fork_point]

            trace_fork.children[state_id] = self._execution_traces.get(state_id, [])

            # If the parent's execution trace is not one we are interested in,
            # stop following it once it forks to a path that we are interested
            # in
            if path_ids and parent_state_id not in path_ids:
                del parent_execution_trace[fork_point + 1:]

        return self._execution_traces[0]

    def _parse_trace_file(self, trace_file, path_ids=None):
        """
        Parse a single ``trace_file``.

        This method will iterate over all of the entries in the given trace
        file. An S2E execution trace file (typically stored in
        ``ExecutionTracer.dat``) is a binary file that contains data recorded
        by S2E's ``ExecutionTracer`` plugins. The trace file is essentially an
        array of ``(header, item)`` tuples. The header (of type
        ``TraceItemHeader``) describes the size and type of the corresponding
        item. Base on this information we can then parse the item and
        instantiate the correct ``TraceEntry`` class.

        The following information is recorded and stored in the class's
        attributes:
            * The execution trace data (a list of ``(TraceItemHeader,
              TraceEntry)`` tuples) for the states found in the ``trace_file``.
            * For each state ID found in the ``trace_file``, record its parent
              state ID. This is so that we can reconstruct the execution tree
              once all of the trace files have been individually parsed.
            * If a state forks, record the "fork point". This is just an index
              into the execution trace list and is also used for reconstructing
              the final execution tree.

        If ``path_ids`` is specified, only states with an ID less than the
        maximum path ID will be saved.
        """
        # The maximum state ID to return an execution trace for
        max_path_id = max(path_ids) if path_ids else None

        # Map of state IDs to the number of entries for that particular
        # state/path. Used for determining fork points.
        path_lengths = {}

        while True:
            raw_header = trace_file.read(TraceItemHeader.static_size())

            # An empty header signifies EOF
            if not raw_header:
                break

            header = TraceItemHeader.deserialize(raw_header)

            # Determine the item's type from the header
            item_type = header.type
            item_class = _TRACE_ENTRY_MAP.get(item_type)
            if not item_class:
                # If an unknown item type is found, just skip it
                logger.warn('Found unknown trace item `%s`. Skipping %d '
                            'bytes...', item_type.value, header.size)
                trace_file.read(header.size)
                continue

            # Read the raw data and deserialize it
            raw_item = trace_file.read(header.size)
            item = item_class.deserialize(raw_item, header.size)

            # Skip any states that have an ID greater than that which we have
            # been asked to parse
            current_state_id = header.state_id
            if path_ids and current_state_id > max_path_id:
                continue

            # If the item is a state fork, we must update the ``_path_info``
            # dictionary with the parent and fork point information
            if item_type == TraceEntryType.TRACE_FORK:
                new_children = {}

                for child_state_id in item.children:
                    # For each child state, save:
                    #   * The state ID of the parent
                    #   * The index into the current state's execution trace
                    #     indicating where the fork occured
                    #   * Create a entry for the new state in the main trace
                    #     dictionary
                    if child_state_id != current_state_id:
                        fork_point = path_lengths.get(current_state_id, 0)
                        self._path_info[child_state_id] = current_state_id, fork_point

                        # When parsed directly from the trace file, the
                        # ``children`` attribute in a ``TraceFork`` object is a
                        # list of state IDs. To correctly represent the
                        # execution trace, we transform this list into a
                        # dictionary mapping state IDs to a new execution trace
                        # (i.e. a list of ``(TraceItemHeader, TraceEntry)``
                        # tuples). This list is initially empty.
                        new_children[child_state_id] = []

                # Since a ``TraceEntry`` is immutable, we have to create a new
                # one if we want to use the ``new_children`` dictionary
                item = trace_entries.TraceFork(item.pc, new_children)

            # Append the ``(TraceItemHeader, TraceEntry)`` tuple to the
            # execution trace for this state
            if current_state_id not in self._execution_traces:
                self._execution_traces[current_state_id] = []
            self._execution_traces[current_state_id].append((header, item))

            # Update the path length information for future fork points
            if current_state_id not in path_lengths:
                path_lengths[current_state_id] = 0
            path_lengths[current_state_id] += 1

    def _get_parent_states(self, state_id):
        """
        Get the list of parent state IDs for the given ``state_id``.
        """
        current_state_id = state_id
        parent_states = []

        while current_state_id:
            current_state_id, _ = self._path_info.get(current_state_id)
            parent_states.append(current_state_id)

        return parent_states


def parse(results_dir, path_ids=None):
    """
    Parse the trace file(s) generated by S2E's execution tracer plugins.

    The ``ExecutionTracer`` plugin will write one or more
    ``ExecutionTracer.dat`` files depending on the number of S2E processes
    created when running S2E. These will be individually parsed by an
    ``ExecutionTraceParser`` and then the results combined to form a single
    execution tree.

    Args:
        results_dir: Path to an ``s2e-out-*`` directory in an analysis project.

    Returns:
        An execution tree of all states executed by S2E.
    """
    # Get the ExecutionTracer.dat file(s). Include both multi-node and single
    # node results
    execution_trace_files = glob.glob(os.path.join(results_dir, '*', 'ExecutionTracer.dat')) + \
                            glob.glob(os.path.join(results_dir, 'ExecutionTracer.dat'))

    if not execution_trace_files:
        logger.warning('No \'ExecutionTrace.dat\' file found in s2e-last. Did '
                       'you enable any trace plugins in s2e-config.lua?')
        return []

    # Parse the execution trace file(s) to construct a single execution tree.
    execution_trace_parser = ExecutionTraceParser(execution_trace_files)
    return execution_trace_parser.parse(path_ids)

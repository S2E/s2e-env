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


import logging

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
    TraceEntryType.TRACE_TB_START: None,
    TraceEntryType.TRACE_TB_END: None,
    TraceEntryType.TRACE_MODULE_DESC: None,
    TraceEntryType.TRACE_FORK: trace_entries.TraceFork,
    TraceEntryType.TRACE_CACHESIM: None,
    TraceEntryType.TRACE_TESTCASE: None,
    TraceEntryType.TRACE_BRANCHCOV: trace_entries.TraceBranchCoverage,
    TraceEntryType.TRACE_MEMORY: trace_entries.TraceMemory,
    TraceEntryType.TRACE_PAGEFAULT: trace_entries.TracePageFault,
    TraceEntryType.TRACE_TLBMISS: trace_entries.TraceTLBMiss,
    TraceEntryType.TRACE_ICOUNT: trace_entries.TraceICount,
    TraceEntryType.TRACE_MEM_CHECKER: trace_entries.TraceMemChecker,
    TraceEntryType.TRACE_EXCEPTION: trace_entries.TraceException,
    TraceEntryType.TRACE_STATE_SWITCH: trace_entries.TraceStateSwitch,
    TraceEntryType.TRACE_TB_START_X64: None,
    TraceEntryType.TRACE_TB_END_X64: None,
    TraceEntryType.TRACE_BLOCK: trace_entries.TraceBlock,
}


def parse(trace_file):
    """
    Parse the given ``trace_file``.

    An S2E execution trace file is a binary-file that contains data recoreded
    by S2E's ``ExecutionTracer`` plugins. The trace file is essentially a list
    of header and item pairs. The header (``TraceItemHeader``) describes the
    size and type of the following item. Based on this information we can then
    parse the item and instantiate the correct class.

    Returns:
        A list of tuples containing:
            1. A ``TraceItemHeader``
            2. The trace data for the header
    """
    filename = trace_file.name
    logger.debug('Parsing %s', filename)

    entries = []
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
            logger.warn('Found unknown trace item %d. Skipping %d bytes...',
                        item_type, header.size)
            trace_file.read(header.size)
            continue

        # Read the raw data and deserialize it
        raw_item = trace_file.read(header.size)
        item = item_class.deserialize(raw_item, header.size)

        entries.append((header, item))

    return entries

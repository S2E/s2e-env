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
import os

from sortedcontainers import SortedDict

from s2e_env.command import ProjectCommand, CommandError
from s2e_env.execution_trace import parse as parse_execution_tree
from s2e_env.execution_trace import TraceEntries_pb2
from s2e_env.execution_trace.analyzer import Analyzer
from s2e_env.execution_trace.modules import Module
from s2e_env.symbols import SymbolManager

logger = logging.getLogger('forkprofile')


class ForkProfiler:
    def __init__(self, trace, syms):
        self._trace = trace
        self._fp = SortedDict()
        self._syms = syms

    @staticmethod
    def _get_module(state, pid, pc):
        try:
            return state.modules.get(pid, pc)
        except Exception as e:
            logger.error(e)
            mod = Module()
            mod.pid = pid
            return mod

    def _trace_cb(self, state, header, item):
        if header.type != TraceEntries_pb2.TRACE_FORK:
            return

        mod = self._get_module(state, header.pid, header.pc)
        logger.debug(mod)

        rel_pc = mod.to_native(header.pc)
        if rel_pc is None:
            rel_pc = header.pc

        counts = {}
        if mod not in self._fp:
            self._fp[mod] = counts
        else:
            counts = self._fp[mod]

        if rel_pc not in counts:
            counts[rel_pc] = 1
        else:
            counts[rel_pc] += 1

    def get(self):
        analyzer = Analyzer(self._trace, self._trace_cb)
        analyzer.walk_tree()

    def get_profile(self):
        fp = []
        for mod, counts in list(self._fp.items()):
            for rel_pc, count in counts.items():
                try:
                    sym, fcn = self._syms.get(mod.path, rel_pc)
                except Exception as e:
                    logger.debug(e, exc_info=1)
                    sym, fcn = None, None

                fp.append((mod, rel_pc, count, sym, fcn))

        return sorted(fp, key=lambda v: -v[2])

    def dump(self):
        profile = self.get_profile()

        print('# The fork profile shows all the program counters where execution forked:')
        print('# process_pid module_path:address fork_count source_file:line_number (function_name)')

        for v in profile:
            mod, rel_pc, count, sym, fcn = v
            if v[3]:
                print('%05d %s:%#010x %4d %s:%d (%s)' % (mod.pid,
                                                         os.path.normpath(mod.path),
                                                         rel_pc,
                                                         count,
                                                         os.path.normpath(sym.filename),
                                                         sym.line,
                                                         fcn.name if fcn else None))
            else:
                print('%05d %s:%#010x %4d (no debug info)' % (mod.pid,
                                                              os.path.normpath(mod.path),
                                                              rel_pc,
                                                              count))


class Command(ProjectCommand):
    """
    Parses an execution trace into JSON.
    """

    help = 'Generates a fork profile from an execution trace'

    def handle(self, *args, **options):
        # Parse the ExecutionTracer.dat file(s) and generate an execution tree
        # for the given path IDs
        results_dir = self.project_path('s2e-last')
        execution_tree = parse_execution_tree(results_dir)
        if not execution_tree:
            raise CommandError('The execution trace is empty')

        syms = SymbolManager(self.install_path(), self.symbol_search_path)

        fp = ForkProfiler(execution_tree, syms)
        fp.get()
        fp.dump()

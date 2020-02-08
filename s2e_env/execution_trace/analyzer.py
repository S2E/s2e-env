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

from s2e_env.execution_trace import TraceEntries_pb2

from .modules import Module, ModuleMap

logger = logging.getLogger('analyzer')


class AnalyzerState:
    def __init__(self, modules=None):
        if not modules:
            modules = ModuleMap()

        self._modules = modules

    @property
    def modules(self):
        return self._modules

    def clone(self):
        return AnalyzerState(self._modules.clone())


class Analyzer:
    """
    This class provides a mechanism to walk execution trees. Walking is done in depth-first order.
    The client is passed a callback that the analyzer calls on every trace item.

    While walking the execution tree, this class builds and exposes state information. For example, it keeps
    track of an up-to-date module map that clients can query to determine to which module a given program
    counter belongs at any point of the execution tree.
    """

    def __init__(self, execution_tree, cb):
        """
        Sets up an instance of the analyzer using the given trace and callback.

        :param execution_tree: tree obtained with the parse_execution_tree function
        :param cb: callback to be invoked on every trace item. First argument is an instance of AnalyzerState,
        the second is the trace item header, the third is the item itself.
        """
        self._tree = execution_tree
        self._cb = cb

    def walk_tree(self):
        stack = []

        stack.append((self._tree, AnalyzerState()))

        while stack:
            trace, state = stack.pop()

            for header, item in trace:
                if header.type == TraceEntries_pb2.TRACE_FORK:
                    for child_trace in item.children.values():
                        ns = state.clone()
                        stack.append((child_trace, ns))
                elif header.type == TraceEntries_pb2.TRACE_OSINFO:
                    state.modules.kernel_start = item.kernel_start
                elif header.type == TraceEntries_pb2.TRACE_MOD_LOAD:
                    mod = Module(item)
                    state.modules.add(mod)
                elif header.type == TraceEntries_pb2.TRACE_MOD_UNLOAD:
                    mod = Module(item)
                    try:
                        state.modules.remove(mod)
                    except Exception:
                        pass

                self._cb(state, header, item)

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

import bisect

from functools import total_ordering


@total_ordering
class FunctionInfoEntry:
    __slots__ = '_name', '_start_addr', '_end_addr'

    def __init__(self, funcname, start_addr, end_addr):
        self._name = funcname
        self._start_addr = start_addr
        self._end_addr = end_addr

    @property
    def name(self):
        return self._name

    @property
    def start(self):
        return self._start_addr

    @property
    def end(self):
        return self._end_addr

    def __hash__(self):
        return hash(self._name)

    def __eq__(self, other):
        return not self < other and not other < self

    def __lt__(self, other):
        # Access fields directly, using properties is too slow
        return self._end_addr < other._start_addr

    def __str__(self):
        return '%s@%#x_%#x' % (self._name, self._start_addr, self._end_addr)


class FunctionInfo:
    """
    This class provides an efficient lookup from address to function name.
    """

    __slots__ = ('_funcs',)

    def __init__(self):
        self._funcs = []

    def _index(self, x):
        # Find rightmost value less than or equal to x
        i = bisect.bisect_right(self._funcs, x)
        if i:
            return i - 1

        raise ValueError

    def add(self, funcname, start, end):
        fcn = FunctionInfoEntry(funcname, start, end)
        bisect.insort(self._funcs, fcn)

    def get(self, addr):
        fcn = FunctionInfoEntry(None, addr, addr+1)
        return self._funcs[self._index(fcn)]

    def to_dict(self):
        out_funcs = {}
        for fcn in self._funcs:
            out_funcs[fcn.name] = (fcn.start, fcn.end)
        return out_funcs

    @staticmethod
    def from_dict(fcns):
        ret = FunctionInfo()
        for name, se in fcns.items():
            ret.add(name, se[0], se[1])
        return ret

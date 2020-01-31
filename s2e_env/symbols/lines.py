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
import logging

from functools import total_ordering

logger = logging.getLogger('lines')


@total_ordering
class LineInfoEntry:
    __slots__ = '_filename', '_line', '_addr'

    def __init__(self, filename, line, addr):
        self._filename = filename
        self._line = line
        self._addr = addr

    @property
    def filename(self):
        return self._filename

    @property
    def line(self):
        return self._line

    @property
    def addr(self):
        return self._addr

    def __hash__(self):
        return self._addr

    def __eq__(self, other):
        return not self < other and not other < self

    def __lt__(self, other):
        # Access fields directly, using properties is too slow
        return self._addr < other._addr

    def __str__(self):
        return '%s:%d (%#x)' % (self._filename, self._line, self._addr)


class LinesByAddr:
    """
    This class maintains a mapping from addresses to line information.
    Lookup and insertion are done using binary search.
    """

    __slots__ = ('_lines',)

    def __init__(self):
        self._lines = []

    def _index(self, x):
        # Find rightmost value less than or equal to x
        i = bisect.bisect_right(self._lines, x)
        if i:
            return i - 1

        raise ValueError

    def add(self, filename, line, addr):
        sym = LineInfoEntry(filename, line, addr)
        bisect.insort(self._lines, sym)

    def get(self, addr):
        sym = LineInfoEntry(None, None, addr)
        return self._lines[self._index(sym)]

    @property
    def lines(self):
        return self._lines

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
import copy
import logging

from functools import total_ordering


logger = logging.getLogger('analyzer')


@total_ordering
class Module(object):
    def __init__(self, name, path, load_base, native_base, size, pid): # pylint: disable=too-many-arguments
        self._name = name
        self._path = path
        self._load_base = load_base
        self._native_base = native_base
        self._size = size
        self._pid = pid

    @property
    def name(self):
        return self._name

    @property
    def path(self):
        return self._path

    @property
    def load_base(self):
        return self._load_base

    @property
    def native_base(self):
        return self._native_base

    @property
    def size(self):
        return self._size

    @property
    def pid(self):
        return self._pid

    def to_native(self, pc):
        return pc - self._load_base + self._native_base

    def __hash__(self):
        return hash((self._pid, self._load_base))

    def __eq__(self, other):
        return not self < other and not other < self

    def __lt__(self, other):
        # pylint: disable=protected-access
        # Access fields directly, using properties is too slow
        if self._pid != other._pid:
            return self._pid < other._pid

        return self._load_base + self._size <= other._load_base

    def __str__(self):
        return 'Module name:%s (%s) load_base:%#x native_base:%#x size:%#x pid:%d' % (
            self.name, self.path, self.load_base, self.native_base, self.size, self.pid)


class ModuleMap(object):
    def __init__(self):
        self._modules = []
        self._kernel_start = None

    def _index(self, x):
        i = bisect.bisect_left(self._modules, x)
        if i != len(self._modules) and self._modules[i] == x:
            return i
        raise ValueError

    def add(self, mod):
        bisect.insort(self._modules, mod)

    def remove(self, mod):
        del self._modules[self._index(mod)]

    def get(self, pid, pc):
        if pc > self._kernel_start:
            pid = 0

        mod = Module(None, None, pc, None, 1, pid)
        return self._modules[self._index(mod)]

    def dump(self):
        for mod in self._modules:
            logger.info(mod)

    def clone(self):
        """
        This assumes that individual modules are immutable, so it's enough
        to just copy the array, without copying the modules themselves.
        """
        # pylint: disable=protected-access
        ret = ModuleMap()
        ret._modules = copy.copy(self._modules)
        ret._kernel_start = self._kernel_start
        return ret

    @property
    def kernel_start(self):
        return self._kernel_start

    @kernel_start.setter
    def kernel_start(self, pc):
        self._kernel_start = pc

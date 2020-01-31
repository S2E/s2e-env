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
class SectionDescriptor:
    __slots__ = (
        'name', 'runtime_load_base', 'native_load_base', 'size',
        'readable', 'writable', 'executable'
    )

    def __init__(self, pb_section):
        if pb_section:
            self.name = pb_section.name
            self.runtime_load_base = pb_section.runtime_load_base
            self.native_load_base = pb_section.native_load_base
            self.size = pb_section.size
            self.readable = pb_section.readable
            self.writable = pb_section.writable
            self.executable = pb_section.executable

    def contains(self, pc):
        return self.runtime_load_base <= pc < (self.runtime_load_base + self.size)

    def __hash__(self):
        return hash((self.runtime_load_base, self.size))

    def __eq__(self, other):
        return not self < other and not other < self

    def __lt__(self, other):
        return self.runtime_load_base + self.size <= other.runtime_load_base

    def __str__(self):
        return 'name:%s rt_base=%#x size=%#x' % (self.name, self.runtime_load_base, self.size)


@total_ordering
class Module:
    __slots__ = (
        'name', 'path', 'pid', 'sections'
    )

    def __init__(self, pb_module=None):
        self.sections = []
        if pb_module:
            self.name = pb_module.name
            self.path = pb_module.path
            self.pid = pb_module.pid
            for section in pb_module.sections:
                self.sections.append(SectionDescriptor(section))
        else:
            self.name = '<unknown>'
            self.path = '<unknown>'
            self.pid = 0

    def get_section(self, pc):
        for section in self.sections:
            if section.contains(pc):
                return section
        return None

    def to_native(self, pc):
        section = self.get_section(pc)
        if not section:
            return None

        return pc - section.runtime_load_base + section.native_load_base

    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        return self.path == other.path and self.name == other.name

    def __lt__(self, other):
        return self.path < other.path

    def __str__(self):
        return 'Module name:%s (%s) pid:%d' % (self.name, self.path, self.pid)


def _index(sections, x):
    i = bisect.bisect_left(sections, x)
    if i != len(sections) and sections[i] == x:
        return i

    return None


class ModuleMap:
    def __init__(self):
        self._pid_to_sections = {}
        self._section_to_module = {}
        self._kernel_start = 0xffffffffffffffff

    def add(self, mod):
        if mod.pid not in self._pid_to_sections:
            self._pid_to_sections[mod.pid] = []

        pid_sections = self._pid_to_sections[mod.pid]

        for section in mod.sections:
            if not section.size:
                raise Exception('Section %s of module %s has zero size' % (section, mod))

            idx = _index(pid_sections, section)
            if idx is not None:
                logger.warning('Section already loaded: %s - module %s',
                               section, self._section_to_module[(mod.pid, pid_sections[idx])])
                continue

            bisect.insort(pid_sections, section)
            self._section_to_module[(mod.pid, section)] = mod

    def remove(self, mod):
        pid_sections = self._pid_to_sections[mod.pid]
        for section in mod.sections:
            idx = _index(pid_sections, section)
            if idx is not None:
                del pid_sections[idx]
                del self._section_to_module[(mod.pid, section)]

    def remove_pid(self, pid):
        del self._pid_to_sections[pid]

    def get(self, pid, pc):
        pid = self._translate_pid(pid, pc)
        if pid not in self._pid_to_sections:
            raise Exception('Could not find pid=%d' % pid)

        sections = self._pid_to_sections[pid]
        sd = SectionDescriptor(None)
        sd.runtime_load_base = pc
        sd.size = 1

        idx = _index(sections, sd)
        if idx is None:
            raise Exception('Could not find section containing address %#x' % pc)

        section = sections[idx]
        return self._section_to_module[(pid, section)]

    def dump(self):
        logger.info('Dumping module map')
        for pid, sections in list(self._pid_to_sections.items()):
            for section in sections:
                s = module = None
                logger.info('pid=%d section=(%s) module=(%s) section=(%s)', pid, section, module, s)
        logger.info('Dumping module map done')

    def clone(self):
        """
        This assumes that individual modules are immutable, so it's enough
        to just copy the array, without copying the modules themselves.
        """
        # pylint: disable=protected-access
        ret = ModuleMap()
        ret._pid_to_sections = copy.deepcopy(self._pid_to_sections)
        ret._section_to_module = copy.deepcopy(self._section_to_module)
        ret._kernel_start = self._kernel_start
        return ret

    def _translate_pid(self, pid, pc):
        if pc >= self._kernel_start:
            return 0
        return pid

    @property
    def kernel_start(self):
        return self._kernel_start

    @kernel_start.setter
    def kernel_start(self, pc):
        self._kernel_start = pc

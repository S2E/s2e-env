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


import struct

from enum import Enum

#
# The following code is a Python adaption of the C++ code in
# libs2eplugins/src/s2e/Plugins/ExecutionTracers/TraceEntries.h
#

class TraceEntryType(Enum):
    """
    The different types of trace entries that can be logged.
    """

    TRACE_MOD_LOAD = 0
    TRACE_MOD_UNLOAD = 1
    TRACE_PROC_UNLOAD = 2
    TRACE_CALL = 3
    TRACE_RET = 4
    TRACE_TB_START = 5
    TRACE_TB_END = 6
    TRACE_MODULE_DESC = 7
    TRACE_FORK = 8
    TRACE_CACHESIM = 9
    TRACE_TESTCASE = 10
    TRACE_BRANCHCOV = 11
    TRACE_MEMORY = 12
    TRACE_PAGEFAULT = 13
    TRACE_TLBMISS = 14
    TRACE_ICOUNT = 15
    TRACE_MEM_CHECKER = 16
    TRACE_EXCEPTION = 17
    TRACE_STATE_SWITCH = 18
    TRACE_TB_START_X64 = 19
    TRACE_TB_END_X64 = 20
    TRACE_BLOCK = 21
    TRACE_MAX = 22


class TraceEntryError(Exception):
    """
    An error occurred with a trace entry.
    """
    pass


class TraceEntry(object):
    """
    Abstract trace entry class.

    Defines how a particular trace entry is serialized when logged and
    deserialized when read from a log.

    Depending on the trace entry type (as defined by the ``TraceEntryType``
    enum), the format of a trace entry may be static or dynamic. If a trace
    entry format is static, then the corresponding trace entry will have a
    consistent size and format whenever it is serialized/deserialized. If a
    trace entry is not static, then the entry probably contains a variable
    number of elements that can only be determined at run-time.

    The static trace entry format is defined in the ``FORMAT`` class attribute
    and its size can be determined using the ``static_size`` class method.

    The dynamic trace entry format is defined in the ``_struct`` attribute
    and its size can be determined using the ``len`` function.

    Note that ``TraceEntry``'s default ``deserialize`` method will only work if
    the trace entry's format can be determined statically. Otherwise the user
    must implement their own deserialize routine (e.g. as is done in the
    ``TraceFork`` class). When calling a custom ``deserialize`` method the
    run-time size of the item **must** be provided.
    """

    FORMAT = None

    def __init__(self, fmt=''):
        self._struct = struct.Struct(fmt)

    def __len__(self):
        """
        The length of the object when serialized.
        """
        return self._struct.size

    def as_dict(self):
        """
        Get a dictionary representation of the trace entry.

        This method should be overwritten.
        """
        return {}

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join('%s=%s' % (key, value) for key, value in self.as_dict().items()))

    @classmethod
    def static_size(cls):
        try:
            return struct.calcsize(cls.FORMAT)
        except struct.error:
            raise TraceEntryError('Cannot statically determine the size of %s' % cls.__name__)

    @classmethod
    def deserialize(cls, data, size=None):
        try:
            unpacked_data = struct.unpack(cls.FORMAT, data)
            return cls(*unpacked_data)
        except struct.error:
            raise TraceEntryError('Cannot deserialize %s data' % cls.__name__)

    def serialize(self):
        """
        Serializes the object using the given ``_struct`` property. The user
        must specify the order that elements are serialized.

        E.g.

        ```
        def serialize(self):
            return self._struct.pack(self._elems['foo'], self._elems['bar'])
        ```
        """
        raise NotImplementedError('Subclasses of TraceEntry must provide a '
                                  'serialize() method')


class TraceItemHeader(TraceEntry):
    FORMAT = '<QIBIQ'

    def __init__(self, timestamp, size, type_, state_id, pid):
        super(TraceItemHeader, self).__init__(TraceItemHeader.FORMAT)
        self._timestamp = timestamp
        self._size = size
        self._type = TraceEntryType(type_)
        self._state_id = state_id
        self._pid = pid

    def serialize(self):
        return self._struct.pack(self._timestamp,
                                 self._size,
                                 self._type,
                                 self._state_id,
                                 self._pid)

    def as_dict(self):
        return {
            'timestamp': self.timestamp,
            'size': self.size,
            'type': self.type,
            'stateId': self.state_id,
            'pid': self.pid,
        }

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def size(self):
        return self._size

    @property
    def type(self):
        return self._type

    @property
    def state_id(self):
        return self._state_id

    @property
    def pid(self):
        return self._pid


class TraceModuleLoad(TraceEntry):
    FORMAT = '<32s256sQQQQQ'

    def __init__(self, name, path, load_base, native_base, size, address_space,
                 pid):
        super(TraceModuleLoad, self).__init__(TraceModuleLoad.FORMAT)
        self._name = name
        self._path = path
        self._load_base = load_base
        self._native_base = native_base
        self._size = size
        self._address_space = address_space
        self._pid = pid

    def serialize(self):
        return self._struct.pack(self._name,
                                 self._path,
                                 self._load_base,
                                 self._native_base,
                                 self._size,
                                 self._address_space,
                                 self._pid)

    def as_dict(self):
        return {
            'name': self.name,
            'path': self.path,
            'loadBase': self.load_base,
            'nativeBase': self.native_base,
            'size': self.size,
            'addressSpace': self.address_space,
            'pid': self.pid,
        }

    @property
    def name(self):
        return self._name.rstrip('\0')

    @property
    def path(self):
        return self._path.rstrip('\0')

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
    def address_space(self):
        return self._address_space

    @property
    def pid(self):
        return self._pid


class TraceModuleUnload(TraceEntry):
    FORMAT = '<Q'

    def __init__(self, load_base):
        super(TraceModuleUnload, self).__init__(TraceModuleUnload.FORMAT)
        self._load_base = load_base

    def serialize(self):
        return self._struct.pack(self._load_base)

    def as_dict(self):
        return {
            'loadBase': self.load_base,
        }

    @property
    def load_base(self):
        return self._load_base


class TraceProcessUnload(TraceEntry):
    FORMAT = '<Q'

    def __init__(self, return_code):
        super(TraceProcessUnload, self).__init__(TraceProcessUnload.FORMAT)
        self._return_code = return_code

    def serialize(self):
        return self._struct.pack(self._return_code)

    def as_dict(self):
        return {
            'returnCode': self.return_code,
        }

    @property
    def return_code(self):
        return self._return_code


class TraceCall(TraceEntry):
    FORMAT = '<QQ'

    def __init__(self, source, target):
        super(TraceCall, self).__init__(TraceCall.FORMAT)
        self._source = source
        self._target = target

    def serialize(self):
        return self._struct.pack(self._source, self._target)

    def as_dict(self):
        return {
            'source': self.source,
            'target': self.target,
        }

    @property
    def source(self):
        return self._source

    @property
    def target(self):
        return self._target


class TraceReturn(TraceEntry):
    FORMAT = '<QQ'

    def __init__(self, source, target):
        super(TraceReturn, self).__init__(TraceReturn.FORMAT)
        self._source = source
        self._target = target

    def serialize(self):
        return self._struct.pack(self._source, self._target)

    def as_dict(self):
        return {
            'source': self.source,
            'target': self.target,
        }

    @property
    def source(self):
        return self._source

    @property
    def target(self):
        return self._target


class TraceFork(TraceEntry):
    FORMAT = '<QI%dI'

    def __init__(self, pc, children):
        super(TraceFork, self).__init__(TraceFork.FORMAT % len(children))
        self._pc = pc
        self._children = children

    @classmethod
    def deserialize(cls, data, size=None):
        if not size:
            raise TraceEntryError('A size must be provided when deserializing '
                                  'a ``TraceFork`` item')
        num_children = (size - struct.calcsize('<QI')) / struct.calcsize('<I')
        unpacked_data = struct.unpack(TraceFork.FORMAT % num_children, data)

        return TraceFork(unpacked_data[0], unpacked_data[2:])

    def serialize(self):
        return self._struct.pack(self._pc,
                                 len(self._children),
                                 *self._children)

    def as_dict(self):
        return {
            'pc': self.pc,
            'children': self.children,
        }

    @property
    def pc(self):
        return self._pc

    @property
    def children(self):
        return self._children


class TraceBranchCoverage(TraceEntry):
    FORMAT = '<QQ'

    def __init__(self, pc, dest_pc):
        super(TraceBranchCoverage, self).__init__(TraceBranchCoverage.FORMAT)
        self._pc = pc
        self._dest_pc = dest_pc

    def serialize(self):
        return self._struct.pack(self._pc, self._dest_pc)

    def as_dict(self):
        return {
            'pc': self.pc,
            'destPc': self.dest_pc,
        }

    @property
    def pc(self):
        return self._pc

    @property
    def dest_pc(self):
        return self._dest_pc


class TraceCacheSimType(Enum):
    CACHE_PARAMS = 0
    CACHE_NAME = 1
    CACHE_ENTRY = 2


class TraceCacheSimParams(TraceEntry):
    FORMAT = '<BIIIII'

    def __init__(self, type_, cache_id, size, line_size, associativity,
                 upper_cache_id):
        super(TraceCacheSimParams, self).__init__(TraceCacheSimParams.FORMAT)
        self._type = type_
        self._cache_id = cache_id
        self._size = size
        self._line_size = line_size
        self._associativity = associativity
        self._upper_cache_id = upper_cache_id

    def serialize(self):
        return self._struct.pack(self._type,
                                 self._cache_id,
                                 self._size,
                                 self._line_size,
                                 self._associativity,
                                 self._upper_cache_id)

    def as_dict(self):
        return {
            'type': self.type,
            'cacheId': self.cache_id,
            'size': self.size,
            'lineSize': self.line_size,
            'associativity': self.associativity,
            'upperCacheId': self.upper_cache_id,
        }

    @property
    def type(self):
        return TraceCacheSimType(self._type)

    @property
    def cache_id(self):
        return self._cache_id

    @property
    def size(self):
        return self._size

    @property
    def line_size(self):
        return self._line_size

    @property
    def associativity(self):
        return self._associativity

    @property
    def upper_cache_id(self):
        return self._upper_cache_id


class TraceCacheSimName(TraceEntry):
    FORMAT = '<BII%ds'

    def __init__(self, type_, id_, name):
        super(TraceCacheSimName, self).__init__(TraceCacheSimName.FORMAT % len(name))
        self._type = type_
        self._id = id_
        self._name = name

    @classmethod
    def deserialize(cls, data, size=None):
        if not size:
            raise TraceEntryError('A size must be provided when deserializing '
                                  'a ``TraceCacheSimName`` item')
        length = (size - struct.calcsize('<BII')) / struct.calcsize('<c')
        unpacked_data = struct.unpack(TraceCacheSimName.FORMAT % length, data)

        return TraceCacheSimName(*unpacked_data)

    def serialize(self):
        return self._struct.pack(self._type,
                                 self._id,
                                 len(self._name),
                                 self._name)

    def as_dict(self):
        return {
            'type': self.type,
            'id': self.id,
            'name': self.name,
        }

    @property
    def type(self):
        return TraceCacheSimType(self._type)

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name


class TraceCacheSimEntry(TraceEntry):
    FORMAT = '<BBQQBBBB'

    def __init__(self, type_, cache_id, pc, address, size, is_write, is_code,
                 miss_count):
        super(TraceCacheSimEntry, self).__init__(TraceCacheSimEntry.FORMAT)
        self._type = type_
        self._cache_id = cache_id
        self._pc = pc
        self._address = address
        self._size = size
        self._is_write = is_write
        self._is_code = is_code
        self._miss_count = miss_count

    def serialize(self):
        return self._struct.pack(self._type,
                                 self._cache_id,
                                 self._pc,
                                 self._address,
                                 self._size,
                                 self._is_write,
                                 self._is_code,
                                 self._miss_count)

    def as_dict(self):
        return {
            'type': self.type,
            'cacheId': self.cache_id,
            'pc': self.pc,
            'address': self.address,
            'size': self.size,
            'isWrite': self.is_write,
            'isCode': self.is_code,
            'missCount': self.miss_count,
        }

    @property
    def type(self):
        return TraceCacheSimType(self._type)

    @property
    def cache_id(self):
        return self._cache_id

    @property
    def pc(self):
        return self._pc

    @property
    def address(self):
        return self._address

    @property
    def size(self):
        return self._size

    @property
    def is_write(self):
        return self._is_write

    @property
    def is_code(self):
        return self._is_code

    @property
    def miss_count(self):
        return self._miss_count


class TraceCache(TraceEntry):
    FORMAT = '<B{params}s%ds{entry}s'.format(params=TraceCacheSimParams.static_size(),
                                             entry=TraceCacheSimEntry.static_size())

    def __init__(self, type_, params, name, entry):
        super(TraceCache, self).__init__(TraceCache.FORMAT % len(name))
        self._type = type_
        self._params = params
        self._name = name
        self._entry = entry

    @classmethod
    def deserialize(cls, data, size=None):
        if not size:
            raise TraceEntryError('A size must be provided when deserializing '
                                  'a ``TraceCache`` item')
        name_length = (size - struct.calcsize('<B') - TraceCacheSimParams.static_size() -
                       TraceCacheSimEntry.static_size()) / struct.calcsize('<c')
        unpacked_data = struct.unpack(TraceCache.FORMAT % name_length, data)

        params = TraceCacheSimParams.deserialize(unpacked_data[1])
        name = TraceCacheSimName.deserialize(unpacked_data[2], name_length)
        entry = TraceCacheSimEntry.deserialize(unpacked_data[3])

        return TraceCache(unpacked_data[0], params, name, entry)

    def serialize(self):
        return self._struct.pack(self._type,
                                 self._params.serialize(),
                                 self._name.serialize(),
                                 self._entry.serialize())

    def as_dict(self):
        return {
            'type': self.type,
            'params': self.params,
            'name': self.name,
            'entry': self.entry,
        }

    @property
    def type(self):
        return self._type

    @property
    def params(self):
        return self._params

    @property
    def name(self):
        return self._name

    @property
    def entry(self):
        return self._entry


class TraceMemChecker(TraceEntry):
    class Flags(Enum):
        GRANT = 1
        REVOKE = 2
        READ = 4
        WRITE = 8
        EXECUTE = 16
        RESOURCE = 32

    FORMAT = '<QIII%ds'

    def __init__(self, start, size, flags, name):
        super(TraceMemChecker, self).__init__(TraceMemChecker.FORMAT)
        self._start = start
        self._size = size
        self._flags = flags
        self._name = name

    @classmethod
    def deserialize(cls, data, size=None):
        if not size:
            raise TraceEntryError('A size must be provided when deserializing '
                                  'a ``TraceMemChecker`` item')
        name_length = (size - struct.calcsize('<QIII')) / struct.calcsize('<c')
        unpacked_data = struct.unpack(TraceMemChecker.FORMAT % name_length, data)

        return TraceMemChecker(*unpacked_data)

    def serialize(self):
        return self._struct.pack(self._start,
                                 self._size,
                                 self._flags,
                                 len(self._name),
                                 self._name)

    def as_dict(self):
        return {
            'start': self.start,
            'size': self.size,
            'flags': self.flags,
            'name': self.name,
        }

    @property
    def start(self):
        return self._start

    @property
    def size(self):
        return self._size

    @property
    def flags(self):
        return self._flags

    @property
    def name(self):
        return self._name


class TraceTestCase(TraceEntry):
    FORMAT = '<II%ds%ds'

    def __init__(self, name, data):
        super(TraceTestCase, self).__init__(TraceTestCase.FORMAT % (len(name), len(data)))
        self._name = name
        self._data = data

    @classmethod
    def deserialize(cls, data, size=None):
        if not size:
            raise TraceEntryError('A size must be provided when deserializing '
                                  'a ``TraceTestCase`` item')
        name_data_size_struct_fmt = '<II'
        name_data_size_struct_size = struct.calcsize(name_data_size_struct_fmt)
        name_size, data_size = struct.unpack(name_data_size_struct_fmt,
                                             data[:name_data_size_struct_size])
        unpacked_data = struct.unpack(TraceTestCase.FORMAT % (name_size, data_size), data)

        return TraceTestCase(*unpacked_data[2:])

    def serialize(self):
        return self._struct.pack(len(self._name),
                                 len(self._data),
                                 self._name,
                                 self._data)

    def as_dict(self):
        return {
            'name': self.name,
            'data': self.data,
        }

    @property
    def name(self):
        return self._name

    @property
    def data(self):
        return self._data


class TraceMemory(TraceEntry):
    FORMAT = '<QQQBBQQ'

    def __init__(self, pc, address, value, size, flags, host_address,
                 concrete_buffer):
        super(TraceMemory, self).__init__(TraceMemory.FORMAT)
        self._pc = pc
        self._address = address
        self._value = value
        self._size = size
        self._flags = flags
        self._host_address = host_address
        self._concrete_buffer = concrete_buffer

    def serialize(self):
        return self._struct.pack(self._pc,
                                 self._address,
                                 self._value,
                                 self._size,
                                 self._flags,
                                 self._host_address,
                                 self._concrete_buffer)

    def as_dict(self):
        return {
            'pc': self.pc,
            'address': self.address,
            'value': self.value,
            'size': self.size,
            'flags': self.flags,
            'hostAddress': self.host_address,
            'concreteBuffer': self.concrete_buffer,
        }

    @property
    def pc(self):
        return self._pc

    @property
    def address(self):
        return self._address

    @property
    def value(self):
        return self._value

    @property
    def size(self):
        return self._size

    @property
    def flags(self):
        return self._flags

    @property
    def host_address(self):
        return self._host_address

    @property
    def concrete_buffer(self):
        return self._concrete_buffer


class TracePageFault(TraceEntry):
    FORMAT = '<QQB'

    def __init__(self, pc, address, is_write):
        super(TracePageFault, self).__init__(TracePageFault.FORMAT)
        self._pc = pc
        self._address = address
        self._is_write = is_write

    def serialize(self):
        return self._struct.pack(self._pc, self._address, self._is_write)

    def as_dict(self):
        return {
            'pc': self.pc,
            'address': self.address,
            'isWrite': self.is_write,
        }

    @property
    def pc(self):
        return self._pc

    @property
    def address(self):
        return self._address

    @property
    def is_write(self):
        return self._is_write


class TraceTLBMiss(TraceEntry):
    FORMAT = '<QQB'

    def __init__(self, pc, address, is_write):
        super(TraceTLBMiss, self).__init__(TraceTLBMiss.FORMAT)
        self._pc = pc
        self._address = address
        self._is_write = is_write

    def serialize(self):
        return self._struct.pack(self._pc, self._address, self._is_write)

    def as_dict(self):
        return {
            'pc': self.pc,
            'address': self.address,
            'isWrite': self.is_write,
        }

    @property
    def pc(self):
        return self._pc

    @property
    def address(self):
        return self._address

    @property
    def is_write(self):
        return self._is_write


class TraceInstructionCount(TraceEntry):
    FORMAT = '<Q'

    def __init__(self, count):
        super(TraceInstructionCount, self).__init__(TraceInstructionCount.FORMAT)
        self._count = count

    def serialize(self):
        return self._struct.pack(self._count)

    def as_dict(self):
        return {
            'count': self.count,
        }

    @property
    def count(self):
        return self._count


class TraceTranslationBlock(TraceEntry):
    class TranslationBlockType(Enum):
        TB_DEFAULT = 0
        TB_JMP = 1
        TB_JMP_IND = 2
        TB_COND_JMP = 3
        TB_COND_JMP_IND = 4
        TB_CALL = 5
        TB_CALL_IND = 6
        TB_REP = 7
        TB_RET = 8

    class X86Registers(Enum):
        EAX = 0
        ECX = 1
        EDX = 2
        EBX = 3
        ESP = 4
        EBP = 5
        ESI = 6
        EDI = 7

    class TranslationBlockFlags(Enum):
        RUNNING_CONCRETE = 1 << 0
        RUNNING_EXCEPTION_EMULATION_CODE = 1 << 1

    FORMAT = '<QQIBBB8Q'

    def __init__(self, pc, target_pc, size, tb_type, flags, symb_mask,
                 registers):
        super(TraceTranslationBlock, self).__init__(TraceTranslationBlock.FORMAT)
        self._pc = pc
        self._target_pc = target_pc
        self._size = size
        self._tb_type = tb_type
        self._flags = flags
        self._symb_mask = symb_mask
        self._registers = registers

    def serialize(self):
        return self._struct.pack(self._pc,
                                 self._target_pc,
                                 self._size,
                                 self._tb_type,
                                 self._flags,
                                 self._symb_mask,
                                 *self._registers)

    def as_dict(self):
        return {
            'pc': self.pc,
            'targetPc': self.target_pc,
            'size': self.size,
            'tbType': self.tb_type,
            'flags': self.flags,
            'symbMask': self.symb_mask,
            'registers': self.registers,
        }

    @property
    def pc(self):
        return self._pc

    @property
    def target_pc(self):
        return self._target_pc

    @property
    def size(self):
        return self._size

    @property
    def tb_type(self):
        return TraceTranslationBlock.TranslationBlockType(self._tb_type)

    @property
    def flags(self):
        return TraceTranslationBlock.TranslationBlockFlags(self._flags)

    @property
    def symb_mask(self):
        return self._symb_mask

    @property
    def registers(self):
        return self._registers


class TraceBlock(TraceEntry):
    class TranslationBlockType(Enum):
        TB_DEFAULT = 0
        TB_JMP = 1
        TB_JMP_IND = 2
        TB_COND_JMP = 3
        TB_COND_JMP_IND = 4
        TB_CALL = 5
        TB_CALL_IND = 6
        TB_REP = 7
        TB_RET = 8

    FORMAT = '<QQB'

    def __init__(self, start_pc, end_pc, tb_type):
        super(TraceBlock, self).__init__(TraceBlock.FORMAT)
        self._start_pc = start_pc
        self._end_pc = end_pc
        self._tb_type = tb_type

    def serialize(self):
        return self._struct.pack(self._start_pc, self._end_pc, self._tb_type)

    def as_dict(self):
        return {
            'startPc': self.start_pc,
            'endPc': self.end_pc,
            'tbType': self.tb_type,
        }

    @property
    def start_pc(self):
        return self._start_pc

    @property
    def end_pc(self):
        return self._end_pc

    @property
    def tb_type(self):
        return TraceBlock.TranslationBlockType(self._tb_type)


class TraceTranslationBlock64(TraceEntry):
    FORMAT = '<SB8Q'

    def __init__(self, base, symb_mask, extended_registers):
        super(TraceTranslationBlock64, self).__init__(TraceTranslationBlock64.FORMAT)
        self._base = base
        self._symb_mask = symb_mask
        self._extended_registers = extended_registers

    def serialize(self):
        return self._struct.pack(self._base.serialize(),
                                 self._symb_mask,
                                 *self._extended_registers)

    def as_dict(self):
        return {
            'base': self.base,
            'symbMask': self.symb_mask,
            'extendedRegisters': self.extended_registers,
        }

    @property
    def base(self):
        return self._base

    @property
    def symb_mask(self):
        return self._symb_mask

    @property
    def extended_registers(self):
        return self._extended_registers


class TraceException(TraceEntry):
    FORMAT = '<QI'

    def __init__(self, pc, vector):
        super(TraceException, self).__init__(TraceException.FORMAT)
        self._pc = pc
        self._vector = vector

    def serialize(self):
        return self._struct.pack(self._pc, self._vector)

    def as_dict(self):
        return {
            'pc': self.pc,
            'vector': self.vector,
        }

    @property
    def pc(self):
        return self._pc

    @property
    def vector(self):
        return self._vector


class TraceStateSwitch(TraceEntry):
    FORMAT = '<I'

    def __init__(self, new_state_id):
        super(TraceStateSwitch, self).__init__(TraceStateSwitch.FORMAT)
        self._new_state_id = new_state_id

    def serialize(self):
        return self._struct.pack(self._new_state_id)

    def as_dict(self):
        return {
            'newStateId': self.new_state_id,
        }

    @property
    def new_state_id(self):
        return self._new_state_id

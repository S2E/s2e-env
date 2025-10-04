from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

CALL_VIOLATION: PbTraceCfiViolationType
DESCRIPTOR: _descriptor.FileDescriptor
RETURN_VIOLATION: PbTraceCfiViolationType
TB_CALL: PbTraceTbType
TB_CALL_IND: PbTraceTbType
TB_COND_JMP: PbTraceTbType
TB_COND_JMP_IND: PbTraceTbType
TB_DEFAULT: PbTraceTbType
TB_EXCP: PbTraceTbType
TB_IRET: PbTraceTbType
TB_JMP: PbTraceTbType
TB_JMP_IND: PbTraceTbType
TB_REP: PbTraceTbType
TB_RET: PbTraceTbType
TB_SYSENTER: PbTraceTbType
TRACE_BLOCK: PbTraceItemHeaderType
TRACE_CACHE_SIM_ENTRY: PbTraceItemHeaderType
TRACE_CACHE_SIM_PARAMS: PbTraceItemHeaderType
TRACE_CFI_STATS: PbTraceItemHeaderType
TRACE_CFI_VIOLATION: PbTraceItemHeaderType
TRACE_EXCEPTION: PbTraceItemHeaderType
TRACE_FORK: PbTraceItemHeaderType
TRACE_ICOUNT: PbTraceItemHeaderType
TRACE_MEMORY: PbTraceItemHeaderType
TRACE_MOD_LOAD: PbTraceItemHeaderType
TRACE_MOD_UNLOAD: PbTraceItemHeaderType
TRACE_OSINFO: PbTraceItemHeaderType
TRACE_PAGEFAULT: PbTraceItemHeaderType
TRACE_PROC_UNLOAD: PbTraceItemHeaderType
TRACE_STATE_SWITCH: PbTraceItemHeaderType
TRACE_TB_END: PbTraceItemHeaderType
TRACE_TB_START: PbTraceItemHeaderType
TRACE_TESTCASE: PbTraceItemHeaderType
TRACE_TLBMISS: PbTraceItemHeaderType

class PbTraceCacheSimEntry(_message.Message):
    __slots__ = ["address", "cache_id", "is_code", "is_write", "miss_count", "pc", "size"]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    CACHE_ID_FIELD_NUMBER: _ClassVar[int]
    IS_CODE_FIELD_NUMBER: _ClassVar[int]
    IS_WRITE_FIELD_NUMBER: _ClassVar[int]
    MISS_COUNT_FIELD_NUMBER: _ClassVar[int]
    PC_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    address: int
    cache_id: int
    is_code: bool
    is_write: bool
    miss_count: int
    pc: int
    size: int
    def __init__(self, cache_id: _Optional[int] = ..., pc: _Optional[int] = ..., address: _Optional[int] = ..., size: _Optional[int] = ..., miss_count: _Optional[int] = ..., is_write: bool = ..., is_code: bool = ...) -> None: ...

class PbTraceCacheSimParams(_message.Message):
    __slots__ = ["associativity", "cache_id", "line_size", "name", "size", "upper_cache_id"]
    ASSOCIATIVITY_FIELD_NUMBER: _ClassVar[int]
    CACHE_ID_FIELD_NUMBER: _ClassVar[int]
    LINE_SIZE_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    UPPER_CACHE_ID_FIELD_NUMBER: _ClassVar[int]
    associativity: int
    cache_id: int
    line_size: int
    name: str
    size: int
    upper_cache_id: int
    def __init__(self, cache_id: _Optional[int] = ..., size: _Optional[int] = ..., line_size: _Optional[int] = ..., associativity: _Optional[int] = ..., upper_cache_id: _Optional[int] = ..., name: _Optional[str] = ...) -> None: ...

class PbTraceCfiStats(_message.Message):
    __slots__ = ["call_and_return_match_count", "call_to_unknown_exec_region_count", "call_violation_count", "direct_call_count", "indirect_call_count", "missing_return_address_count", "pending_violations_count", "ret_count", "ret_from_unknown_exec_region_count", "ret_to_call_site", "ret_to_parent_with_displacement_count", "ret_to_unknown_exec_region_count", "ret_violation_count", "whitelisted_call_pattern_count", "whitelisted_return_count"]
    CALL_AND_RETURN_MATCH_COUNT_FIELD_NUMBER: _ClassVar[int]
    CALL_TO_UNKNOWN_EXEC_REGION_COUNT_FIELD_NUMBER: _ClassVar[int]
    CALL_VIOLATION_COUNT_FIELD_NUMBER: _ClassVar[int]
    DIRECT_CALL_COUNT_FIELD_NUMBER: _ClassVar[int]
    INDIRECT_CALL_COUNT_FIELD_NUMBER: _ClassVar[int]
    MISSING_RETURN_ADDRESS_COUNT_FIELD_NUMBER: _ClassVar[int]
    PENDING_VIOLATIONS_COUNT_FIELD_NUMBER: _ClassVar[int]
    RET_COUNT_FIELD_NUMBER: _ClassVar[int]
    RET_FROM_UNKNOWN_EXEC_REGION_COUNT_FIELD_NUMBER: _ClassVar[int]
    RET_TO_CALL_SITE_FIELD_NUMBER: _ClassVar[int]
    RET_TO_PARENT_WITH_DISPLACEMENT_COUNT_FIELD_NUMBER: _ClassVar[int]
    RET_TO_UNKNOWN_EXEC_REGION_COUNT_FIELD_NUMBER: _ClassVar[int]
    RET_VIOLATION_COUNT_FIELD_NUMBER: _ClassVar[int]
    WHITELISTED_CALL_PATTERN_COUNT_FIELD_NUMBER: _ClassVar[int]
    WHITELISTED_RETURN_COUNT_FIELD_NUMBER: _ClassVar[int]
    call_and_return_match_count: int
    call_to_unknown_exec_region_count: int
    call_violation_count: int
    direct_call_count: int
    indirect_call_count: int
    missing_return_address_count: int
    pending_violations_count: int
    ret_count: int
    ret_from_unknown_exec_region_count: int
    ret_to_call_site: int
    ret_to_parent_with_displacement_count: int
    ret_to_unknown_exec_region_count: int
    ret_violation_count: int
    whitelisted_call_pattern_count: int
    whitelisted_return_count: int
    def __init__(self, direct_call_count: _Optional[int] = ..., indirect_call_count: _Optional[int] = ..., ret_count: _Optional[int] = ..., call_violation_count: _Optional[int] = ..., ret_violation_count: _Optional[int] = ..., ret_from_unknown_exec_region_count: _Optional[int] = ..., ret_to_unknown_exec_region_count: _Optional[int] = ..., missing_return_address_count: _Optional[int] = ..., call_and_return_match_count: _Optional[int] = ..., whitelisted_return_count: _Optional[int] = ..., pending_violations_count: _Optional[int] = ..., whitelisted_call_pattern_count: _Optional[int] = ..., ret_to_parent_with_displacement_count: _Optional[int] = ..., call_to_unknown_exec_region_count: _Optional[int] = ..., ret_to_call_site: _Optional[int] = ...) -> None: ...

class PbTraceCfiViolation(_message.Message):
    __slots__ = ["destination", "expected_destination", "source", "type"]
    DESTINATION_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_DESTINATION_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    destination: PbTraceViolationPcInfo
    expected_destination: PbTraceViolationPcInfo
    source: PbTraceViolationPcInfo
    type: PbTraceCfiViolationType
    def __init__(self, type: _Optional[_Union[PbTraceCfiViolationType, str]] = ..., source: _Optional[_Union[PbTraceViolationPcInfo, _Mapping]] = ..., destination: _Optional[_Union[PbTraceViolationPcInfo, _Mapping]] = ..., expected_destination: _Optional[_Union[PbTraceViolationPcInfo, _Mapping]] = ...) -> None: ...

class PbTraceException(_message.Message):
    __slots__ = ["pc", "vector"]
    PC_FIELD_NUMBER: _ClassVar[int]
    VECTOR_FIELD_NUMBER: _ClassVar[int]
    pc: int
    vector: int
    def __init__(self, pc: _Optional[int] = ..., vector: _Optional[int] = ...) -> None: ...

class PbTraceInstructionCount(_message.Message):
    __slots__ = ["count"]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    count: int
    def __init__(self, count: _Optional[int] = ...) -> None: ...

class PbTraceItemFork(_message.Message):
    __slots__ = ["children"]
    CHILDREN_FIELD_NUMBER: _ClassVar[int]
    children: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, children: _Optional[_Iterable[int]] = ...) -> None: ...

class PbTraceItemHeader(_message.Message):
    __slots__ = ["address_space", "pc", "pid", "state_id", "tid", "timestamp", "type"]
    ADDRESS_SPACE_FIELD_NUMBER: _ClassVar[int]
    PC_FIELD_NUMBER: _ClassVar[int]
    PID_FIELD_NUMBER: _ClassVar[int]
    STATE_ID_FIELD_NUMBER: _ClassVar[int]
    TID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    address_space: int
    pc: int
    pid: int
    state_id: int
    tid: int
    timestamp: int
    type: PbTraceItemHeaderType
    def __init__(self, state_id: _Optional[int] = ..., timestamp: _Optional[int] = ..., address_space: _Optional[int] = ..., pid: _Optional[int] = ..., tid: _Optional[int] = ..., pc: _Optional[int] = ..., type: _Optional[_Union[PbTraceItemHeaderType, str]] = ...) -> None: ...

class PbTraceMemoryAccess(_message.Message):
    __slots__ = ["address", "concrete_buffer", "flags", "host_address", "pc", "size", "value"]
    class Flags(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    CONCRETE_BUFFER_FIELD_NUMBER: _ClassVar[int]
    EXECTRACE_MEM_HASHOSTADDR: PbTraceMemoryAccess.Flags
    EXECTRACE_MEM_INVALID: PbTraceMemoryAccess.Flags
    EXECTRACE_MEM_IO: PbTraceMemoryAccess.Flags
    EXECTRACE_MEM_OBJECTSTATE: PbTraceMemoryAccess.Flags
    EXECTRACE_MEM_SYMBADDR: PbTraceMemoryAccess.Flags
    EXECTRACE_MEM_SYMBHOSTADDR: PbTraceMemoryAccess.Flags
    EXECTRACE_MEM_SYMBVAL: PbTraceMemoryAccess.Flags
    EXECTRACE_MEM_WRITE: PbTraceMemoryAccess.Flags
    FLAGS_FIELD_NUMBER: _ClassVar[int]
    HOST_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    PC_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    address: int
    concrete_buffer: int
    flags: int
    host_address: int
    pc: int
    size: int
    value: int
    def __init__(self, pc: _Optional[int] = ..., address: _Optional[int] = ..., value: _Optional[int] = ..., size: _Optional[int] = ..., flags: _Optional[int] = ..., host_address: _Optional[int] = ..., concrete_buffer: _Optional[int] = ...) -> None: ...

class PbTraceModuleLoadUnload(_message.Message):
    __slots__ = ["address_space", "name", "path", "pid", "sections"]
    class Section(_message.Message):
        __slots__ = ["executable", "name", "native_load_base", "readable", "runtime_load_base", "size", "writable"]
        EXECUTABLE_FIELD_NUMBER: _ClassVar[int]
        NAME_FIELD_NUMBER: _ClassVar[int]
        NATIVE_LOAD_BASE_FIELD_NUMBER: _ClassVar[int]
        READABLE_FIELD_NUMBER: _ClassVar[int]
        RUNTIME_LOAD_BASE_FIELD_NUMBER: _ClassVar[int]
        SIZE_FIELD_NUMBER: _ClassVar[int]
        WRITABLE_FIELD_NUMBER: _ClassVar[int]
        executable: bool
        name: str
        native_load_base: int
        readable: bool
        runtime_load_base: int
        size: int
        writable: bool
        def __init__(self, name: _Optional[str] = ..., runtime_load_base: _Optional[int] = ..., native_load_base: _Optional[int] = ..., size: _Optional[int] = ..., readable: bool = ..., writable: bool = ..., executable: bool = ...) -> None: ...
    ADDRESS_SPACE_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    PID_FIELD_NUMBER: _ClassVar[int]
    SECTIONS_FIELD_NUMBER: _ClassVar[int]
    address_space: int
    name: str
    path: str
    pid: int
    sections: _containers.RepeatedCompositeFieldContainer[PbTraceModuleLoadUnload.Section]
    def __init__(self, name: _Optional[str] = ..., path: _Optional[str] = ..., pid: _Optional[int] = ..., address_space: _Optional[int] = ..., sections: _Optional[_Iterable[_Union[PbTraceModuleLoadUnload.Section, _Mapping]]] = ...) -> None: ...

class PbTraceOsInfo(_message.Message):
    __slots__ = ["kernel_start"]
    KERNEL_START_FIELD_NUMBER: _ClassVar[int]
    kernel_start: int
    def __init__(self, kernel_start: _Optional[int] = ...) -> None: ...

class PbTraceProcessUnload(_message.Message):
    __slots__ = ["return_code"]
    RETURN_CODE_FIELD_NUMBER: _ClassVar[int]
    return_code: int
    def __init__(self, return_code: _Optional[int] = ...) -> None: ...

class PbTraceRegisterData(_message.Message):
    __slots__ = ["symb_mask", "values"]
    SYMB_MASK_FIELD_NUMBER: _ClassVar[int]
    VALUES_FIELD_NUMBER: _ClassVar[int]
    symb_mask: int
    values: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, symb_mask: _Optional[int] = ..., values: _Optional[_Iterable[int]] = ...) -> None: ...

class PbTraceSimpleMemoryAccess(_message.Message):
    __slots__ = ["address", "is_write", "pc"]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    IS_WRITE_FIELD_NUMBER: _ClassVar[int]
    PC_FIELD_NUMBER: _ClassVar[int]
    address: int
    is_write: bool
    pc: int
    def __init__(self, pc: _Optional[int] = ..., address: _Optional[int] = ..., is_write: bool = ...) -> None: ...

class PbTraceStateSwitch(_message.Message):
    __slots__ = ["new_state"]
    NEW_STATE_FIELD_NUMBER: _ClassVar[int]
    new_state: int
    def __init__(self, new_state: _Optional[int] = ...) -> None: ...

class PbTraceTbData(_message.Message):
    __slots__ = ["first_pc", "last_pc", "size", "tb_type"]
    FIRST_PC_FIELD_NUMBER: _ClassVar[int]
    LAST_PC_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    TB_TYPE_FIELD_NUMBER: _ClassVar[int]
    first_pc: int
    last_pc: int
    size: int
    tb_type: PbTraceTbType
    def __init__(self, tb_type: _Optional[_Union[PbTraceTbType, str]] = ..., first_pc: _Optional[int] = ..., last_pc: _Optional[int] = ..., size: _Optional[int] = ...) -> None: ...

class PbTraceTestCase(_message.Message):
    __slots__ = ["items"]
    class KeyValue(_message.Message):
        __slots__ = ["key", "value"]
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: bytes
        def __init__(self, key: _Optional[str] = ..., value: _Optional[bytes] = ...) -> None: ...
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[PbTraceTestCase.KeyValue]
    def __init__(self, items: _Optional[_Iterable[_Union[PbTraceTestCase.KeyValue, _Mapping]]] = ...) -> None: ...

class PbTraceTranslationBlock(_message.Message):
    __slots__ = ["last_pc", "pc", "size", "tb_type"]
    LAST_PC_FIELD_NUMBER: _ClassVar[int]
    PC_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    TB_TYPE_FIELD_NUMBER: _ClassVar[int]
    last_pc: int
    pc: int
    size: int
    tb_type: PbTraceTbType
    def __init__(self, pc: _Optional[int] = ..., last_pc: _Optional[int] = ..., size: _Optional[int] = ..., tb_type: _Optional[_Union[PbTraceTbType, str]] = ...) -> None: ...

class PbTraceTranslationBlockEnd(_message.Message):
    __slots__ = ["data", "regs"]
    DATA_FIELD_NUMBER: _ClassVar[int]
    REGS_FIELD_NUMBER: _ClassVar[int]
    data: PbTraceTbData
    regs: PbTraceRegisterData
    def __init__(self, data: _Optional[_Union[PbTraceTbData, _Mapping]] = ..., regs: _Optional[_Union[PbTraceRegisterData, _Mapping]] = ...) -> None: ...

class PbTraceTranslationBlockStart(_message.Message):
    __slots__ = ["data", "regs"]
    DATA_FIELD_NUMBER: _ClassVar[int]
    REGS_FIELD_NUMBER: _ClassVar[int]
    data: PbTraceTbData
    regs: PbTraceRegisterData
    def __init__(self, data: _Optional[_Union[PbTraceTbData, _Mapping]] = ..., regs: _Optional[_Union[PbTraceRegisterData, _Mapping]] = ...) -> None: ...

class PbTraceViolationPcInfo(_message.Message):
    __slots__ = ["disassembly", "module_path", "module_pc", "pc"]
    DISASSEMBLY_FIELD_NUMBER: _ClassVar[int]
    MODULE_PATH_FIELD_NUMBER: _ClassVar[int]
    MODULE_PC_FIELD_NUMBER: _ClassVar[int]
    PC_FIELD_NUMBER: _ClassVar[int]
    disassembly: str
    module_path: str
    module_pc: int
    pc: int
    def __init__(self, pc: _Optional[int] = ..., module_path: _Optional[str] = ..., module_pc: _Optional[int] = ..., disassembly: _Optional[str] = ...) -> None: ...

class PbTraceItemHeaderType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []

class PbTraceTbType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []

class PbTraceCfiViolationType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []

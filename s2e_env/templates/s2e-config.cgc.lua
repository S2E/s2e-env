--[[
This is CGC-specific configuration. The default settings are very close to
those that were used during the CGC final event.
]]--


-------------------------------------------------------------------------------
-- LinuxMonitor is a plugin that monitors Linux events and exposes them
-- to other plugins in a generic way. Events include process load/termination,
-- thread events, signals, etc.
--
-- LinuxMonitor requires a custom Linux kernel with S2E extensions. This kernel
-- (and corresponding VM image) can be built with S2E tools. Please refer to
-- the documentation for more details.

add_plugin("LinuxMonitor")
pluginsConfig.LinuxMonitor = {
    -- Kill the execution state when it encounters a segfault
    terminateOnSegfault = true,

    -- Kill the execution state when it encounters a trap
    terminateOnTrap = true,
}

-------------------------------------------------------------------------------
-- This plugin is to monitor events from Decree binaries.
-- S2E does not use the old CGC Linux kernel to run Decree binaries. Instead,
-- it uses a custom user-space loader that emulates Decree syscalls. Decree binaries
-- run otherwise like any other statically-linked Linux binaries.
-- That loader is instrumented in order to communicate important events
-- to DecreeMonitor. Instrumented events include CB loading/unloading, syscall
-- invocation, etc.

add_plugin("DecreeMonitor")
pluginsConfig.DecreeMonitor = {
    -- Kill state
    terminateOnSegFault = true,

    handleSymbolicAllocateSize = true,
    handleSymbolicBufferSize = true,

    -- How many read calls can be issued on a single path. The state is killed
    -- when it's exceeded
    maxReadLimitCount = 1000,

    -- How many read calls can return symbolic data. When this is exceeded, use
    -- random inputs
    symbolicReadLimitCount = 512,
}

-------------------------------------------------------------------------------
-- This plugin exports CGC-specific events to a QMP-based web services.
-- Events include generated proofs of vulnerability (PoVs), code coverage,
-- call site information, etc.

add_plugin("CGCInterface")
pluginsConfig.CGCInterface = {
    maxPovCount = 10,
    pobSendInterval = 10000,

    disableSendingExtraDataToDB = false,
    recordConstraints = false,
}

-------------------------------------------------------------------------------
-- This plugin reads LUA configuration files that hold the statically-computed
-- CFG of the binaries. This CFG can be obtained from IDA using the McSema
-- scripts.
--
-- TODO: integrate static analysis into s2e-env
--
-- Note: absence of CFG information is not critical for vulnerability finding.

add_plugin("ControlFlowGraph")
pluginsConfig.ControlFlowGraph = {
    reloadConfig = false,
}


-------------------------------------------------------------------------------
-- This plugin tracks basic block coverage for each state. It requires the
-- ControlFlowGraph plugin in order to convert translation block addresses
-- into basic blocks.
--
-- Note: absence of CFG information is not critical for vulnerability finding.
-- If there is no CFG information, use the TranslationBlockCoverage plugin,
-- which provides a good enough approximation for most purposes.

add_plugin("BasicBlockCoverage")

-------------------------------------------------------------------------------
-- This is the actual PoV generation logic. It currently supports the DARPA
-- Decree CGC formats, both *.c and *.xml.
add_plugin("DecreePovGenerator")

-------------------------------------------------------------------------------
-- The stack monitor plugin instruments function calls and returns in order
-- to keep track of call stacks, stack frames, etc. Interested plugins can
-- use StackMonitor to get information about the current call stack.
--
-- Note: this plugin is currently only enabled for Decree, as it does not
-- support Linux properly (probably a signal issue).
add_plugin("StackMonitor")


-------------------------------------------------------------------------------
-- Override default config
pluginsConfig.ProcessExecutionDetector = {
    moduleNames = {
        "cgcload",
    },
}

pluginsConfig.ModuleExecutionDetector = {
    mod_0 = {
        moduleName = "cgcload",
    },
    logLevel="info"
}
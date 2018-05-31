--[[
This is CGC-specific configuration. The default settings are very close to
those that were used during the CGC final event.
]]--

-------------------------------------------------------------------------------
-- This plugin is to be used together with the Decree Linux Kernel.
-- The Decree kernel has a custom binary loader for challenge binaries (CBs).
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

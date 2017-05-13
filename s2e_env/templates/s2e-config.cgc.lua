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
-- This plugin aggregates different sources of vulnerability information and
-- uses it to generate PoVs.

add_plugin("ExploitGenerator")

-- This is the actual PoV generation logic. It currently supports the DARPA
-- Decree CGC formats, both *.c and *.xml.

add_plugin("POVGenerator")
pluginsConfig.POVGenerator = {
    generatePOVFiles = true,
}

-------------------------------------------------------------------------------
-- The Recipe plugin continuously monitors execution and looks for states
-- that can be exploited. The most important marker of a vulnerability is
-- dereferencing a symbolic pointer. The recipe plugin then constrains that
-- symbolic pointer in a way that forces program execution into a state that
-- was negotiated with the CGC framework.

add_plugin("Recipe")
pluginsConfig.Recipe = {
    recipesDir = "{{ recipes_dir }}",
}

-------------------------------------------------------------------------------
-- The stack monitor plugin instruments function calls and returns in order
-- to keep track of call stacks, stack frames, etc. Interested plugins can
-- use StackMonitor to get information about the current call stack.

add_plugin("StackMonitor")

-------------------------------------------------------------------------------
-- This plugin monitors call sites, i.e., pairs of source-destination program
-- counters. It is useful to recover information about indirect control flow,
-- which is hard to compute statically.

add_plugin("CallSiteMonitor")
pluginsConfig.CallSiteMonitor = {
    dumpInterval = 5,
}


-------------------------------------------------------------------------------
-- Override default CUPASearcher settings with CGC-specific ones.
pluginsConfig.CUPASearcher = {
    logLevel = "info",
    enabled = true,
    classes = {
        "seed",

        -- This class is used with the Recipe plugin in order to prioritize
        -- states that have a high chance of containing a vulnerability.
        "group",
        "pagedir",
        "pc",
    },
}

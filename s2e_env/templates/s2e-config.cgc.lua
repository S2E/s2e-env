add_plugin("BasicBlockCoverage")
add_plugin("StackMonitor")

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

add_plugin("CGCInterface")
pluginsConfig.CGCInterface = {
    maxPovCount = 10,
    pobSendInterval = 10000,

    -- Seeds with priority equal to or lower than the threshold are considered
    -- low priority. For the CFE, high priorities range from 10 to 7 (various
    -- types of POVs and crashes), while normal test cases are from 6 and
    -- below
    lowPrioritySeedThreshold = 6,

    disableSendingExtraDataToDB = false,
    recordConstraints = false,
}

add_plugin("ExploitGenerator")
add_plugin("POVGenerator")
pluginsConfig.POVGenerator = {
    generatePOVFiles = true,
}

add_plugin("Recipe")
pluginsConfig.Recipe = {
    recipesDir = "{{ project_dir }}/recipes",
}

add_plugin("CallSiteMonitor")
pluginsConfig.CallSiteMonitor = {
    dumpInterval = 5,
}


add_plugin("ControlFlowGraph")
pluginsConfig.ControlFlowGraph = {
    reloadConfig = false,
}

-- Override default CUPASearcher settings
pluginsConfig.CUPASearcher = {
    logLevel = "info",
    enabled = true,
    classes = {
        -- This ensures that seed state 0 is kept out of scheduling unless
        -- instructed by SeedSearcher
        "seed",
        -- Recipe uses this to group high priority states
        "group",
        -- Must always split by page dir, to account for multi-bin CBs
        "pagedir",
        -- Prioritize states that have the lowest syscall read count
        "pc",
    },
}

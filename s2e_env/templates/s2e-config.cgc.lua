--
-- This file was automatically generatd by s2e-env at
-- {{ current_time | datetimefilter }}
--
-- Changes can be made by the user where appropriate
--

s2e = {
    logging = {
        console = "debug",
        logLevel = "debug",
    },
    kleeArgs = {
    },
}

plugins = {
    "BaseInstructions",
    "HostFiles",
    "Vmi",

    -- Basic tracing required for test-case generation
    "ExecutionTracer",
    "ModuleTracer",

    -----------------------
    -- CGC-specific plugins
    "CGCInterface",
    "DecreeMonitor",
    "POVGenerator",
    "Recipe",
    "ExploitGenerator",
    -----------------------

    "ModuleExecutionDetector",
    "ProcessExecutionDetector",
    "FunctionMonitor",

    "ForkLimiter",

    "CallSiteMonitor",

    -- This is needed to work around missing CFG information when there is no
    -- way to compute BB coverage
    "TranslationBlockCoverage",

    "BasicBlockCoverage",

    "ControlFlowGraph",

    "MultiSearcher",
    "CUPASearcher",
    "SeedSearcher",

    "StackMonitor",
    "KeyValueStore",
}

pluginsConfig = {}

pluginsConfig.HostFiles = {
    baseDirs = {
        "{{ project_dir }}",
        "{{ project_dir }}/seeds",
    },
    allowWrite = true,
}

pluginsConfig.Vmi = {
    baseDirs = {
        "{{ project_dir }}",
    },
}

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

pluginsConfig.POVGenerator = {
    generatePOVFiles = true,
}

pluginsConfig.Recipe = {
    recipesDir = "{{ project_dir }}/recipes",
}

pluginsConfig.ModuleExecutionDetector = {
    mod_0 = {
        moduleName = "{{ target }}",
        kernelMode = false,
    },
}

pluginsConfig.ProcessExecutionDetector = {
    moduleNames = {
        "{{ target }}",
    },
}

pluginsConfig.ForkLimiter = {
    maxForkCount = 1,
    processForkDelay = 5,
}

pluginsConfig.CallSiteMonitor = {
    dumpInterval = 5,
}

pluginsConfig.ControlFlowGraph = {
    reloadConfig = false,
}

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

pluginsConfig.SeedSearcher = {
    enableSeeds = true,
    seedDirectory = "{{ project_dir }}/seeds",
}

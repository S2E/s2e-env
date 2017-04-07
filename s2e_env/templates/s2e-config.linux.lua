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

    "ModuleExecutionDetector",
    "ProcessExecutionDetector",

    "LinuxMonitor",

    {% if use_seeds == true %}
    "SeedSearcher",
    "MultiSearcher",
    "CUPASearcher",
    "FunctionMonitor",
    {% endif %}

    {% if function_models == true %}
    -- If state explosion becomes a problem, consider uncommenting the
    -- following line to enable the FunctionModels plugin
    -- "FunctionModels",
    {% endif %}
}

pluginsConfig = {}

pluginsConfig.HostFiles = {
    baseDirs = {
        "{{ project_dir }}",
        {% if use_seeds == true %}
        "{{ project_dir }}/seeds",
        {% endif %}
    },
    allowWrite = true,
}

pluginsConfig.Vmi = {
    baseDirs = {
        "{{ project_dir }}",
    },
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

pluginsConfig.LinuxMonitor = {
    terminateOnSegFault = true,
    terminateOnTrap = true,
}

{% if use_seeds == true %}
pluginsConfig.SeedSearcher = {
    seedDirectory = "{{ project_dir }}/seeds",
    enableSeeds = true,
    maxSeedStates = 1000,
}

pluginsConfig.CUPASearcher = {
    enabled = false,
    classes = {
        -- This ensures that seed state 0 is kept out of scheduling unless
        -- instructed by SeedSearcher
        "seed",
        -- Prioritize states that have the lowest syscall read count
        "pc",
    },
}
{% endif %}


dofile('library.lua')

add_plugin("BaseInstructions")

--------------------------------------------------------
table.insert(plugins, "HostFiles")
pluginsConfig.HostFiles = {
    baseDirs = {
        "{{ project_dir }}",
        {% if use_seeds == true %}
        "{{ project_dir }}/seeds",
        {% endif %}
    },
    allowWrite = true,
}

--------------------------------------------------------
add_plugin("Vmi")
pluginsConfig.Vmi = {
    baseDirs = {
        "{{ project_dir }}",
    },
}

--------------------------------------------------------
add_plugin("WebServiceInterface")
pluginsConfig.WebServiceInterface = {
    statsUpdateInterval = 2
}

--------------------------------------------------------
add_plugin("ExecutionTracer")

--------------------------------------------------------
add_plugin("ModuleTracer")

--------------------------------------------------------
add_plugin("TranslationBlockCoverage")

--------------------------------------------------------
add_plugin("ModuleExecutionDetector")
pluginsConfig.ModuleExecutionDetector = {
    mod_0 = {
        moduleName = "{{ target }}",
        kernelMode = false,
    },
}

--------------------------------------------------------
add_plugin("ProcessExecutionDetector")
pluginsConfig.ProcessExecutionDetector = {
    moduleNames = {
        "{{ target }}",
    },
}

--------------------------------------------------------
-- Use CUPA searcher as the default one, it works much better than DFS
add_plugin("CUPASearcher")
add_plugin("MultiSearcher")
pluginsConfig.CUPASearcher = {
    -- The order of classes is important, please refer to the plugin
    -- source code and documentation for details on how CUPA works.
    classes = {
        {% if use_seeds == true %}
        -- This ensures that seed state 0 is kept out of scheduling unless
        -- instructed by SeedSearcher
        "seed",
        {% endif %}

        -- Must always split by page dir, to account for forks in multiple binaries
        "pagedir",
        "pc",
    },
    logLevel="info"
}

{% if use_seeds == true %}
add_plugin("MultiSearcher")
add_plugin("SeedSearcher")
pluginsConfig.SeedSearcher = {
    enableSeeds = true,
    seedDirectory = "{{ project_dir }}/seeds",
}
{% endif %}

--------------------------------------------------------
add_plugin("StaticFunctionModels")

pluginsConfig.StaticFunctionModels = {
  modules = {}
}

g_function_models = {}
safe_load('models.lua')
pluginsConfig.StaticFunctionModels.modules = g_function_models

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
    "LinuxMonitor",
    "TestCaseGenerator"

    {% if function_models == true %}
    -- If state explosion becomes a problem, consider uncommenting the
    -- following line to enable the FunctionModels plugin
    -- "FunctionModels",
    {% endif %}
}

pluginsConfig = {}

{% include 's2e-config.common.lua' %}

pluginsConfig.LinuxMonitor = {
    terminateOnSegFault = true,
    terminateOnTrap = true,
}

pluginsConfig.TestCaseGenerator = {
    generateOnStateKill = true,
    generateOnSegfault = true
}

pluginsConfig.TranslationBlockCoverage = {
    writeCoverageOnStateKill = true,
}

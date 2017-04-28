--------------------------------------------------------
add_plugin("LinuxMonitor")
pluginsConfig.LinuxMonitor = {
    terminateOnSegFault = true,
    terminateOnTrap = true,
}

--------------------------------------------------------
add_plugin("TestCaseGenerator")
pluginsConfig.TestCaseGenerator = {
    generateOnStateKill = true,
    generateOnSegfault = true
}

pluginsConfig.TranslationBlockCoverage = {
    writeCoverageOnStateKill = true,
}

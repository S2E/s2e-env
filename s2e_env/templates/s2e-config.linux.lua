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

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

{% if enable_pov_generation %}

-------------------------------------------------------------------------------
-- This plugin writes PoVs as input files. This is suitable for programs that
-- take their inputs from files (instead of stdin or other methods).
add_plugin("FilePovGenerator")
pluginsConfig.FilePovGenerator = {
    -- The generated PoV will set the program counter
    -- of the vulnerable program to this value
    target_pc = 0x0011223344556677,

    -- The generated PoV will set a general purpose register
    -- of the vulnerable program to this value.
    target_gp = 0x8899aabbccddeeff
}

{% endif %}

-------------------------------------------------------------------------------
-- Monitors Windows events intercepted by the s2e.sys driver.

add_plugin("WindowsMonitor")

-------------------------------------------------------------------------------
-- Keeps for each state an updated map of all the loaded modules.
add_plugin("ModuleMap")

-------------------------------------------------------------------------------
-- This plugin is required to intercept some Windows kernel functions.
-- Guest code patching monitors execution and transparently changes
-- the target program counter when it encounters a call instructions.

add_plugin("GuestCodePatching")
pluginsConfig.GuestCodePatching = {
  moduleNames = {"ntoskrnl.exe", "ntkrnlpa.exe"},
  allowSelfCalls = true
}

{% for m in modules %}
    {% if m[1] %}
        -- Instrument kernel driver {{m[0]}} for fault injection
        table.insert(pluginsConfig.GuestCodePatching["moduleNames"], "{{m[0]}}")
    {% endif %}
{% endfor %}

-- Add an extra option to the existing config
pluginsConfig.ModuleExecutionDetector['trackAllModules'] = true

-------------------------------------------------------------------------------
-- This plugin monitors kernel crashes and generates WinDbg crash dumps.
-- The dump contains the entire physical memory

add_plugin("BlueScreenInterceptor")
add_plugin("WindowsCrashDumpGenerator")

-------------------------------------------------------------------------------
-- This plugin collects Windows crash events (user and kernel space).
-- It must be used together with s2e.sys and drvctl.exe.

add_plugin("WindowsCrashMonitor")
pluginsConfig.WindowsCrashMonitor = {
    terminateOnCrash = true,

    -- Make this true if you want crashes.
    -- Note that crashes may be very large (100s of MBs)
    generateCrashDump = false,

    -- Limit number of crashes we generate
    maxCrashDumps = 10,

    -- Uncompressed dumps have the same size as guest memory (e.g., 2GB),
    -- you almost always want to compress them.
    compressDumps = true
}
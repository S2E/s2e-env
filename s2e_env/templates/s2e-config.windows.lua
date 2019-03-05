-------------------------------------------------------------------------------
-- Monitors Windows events intercepted by the s2e.sys driver.

add_plugin("WindowsMonitor")

-------------------------------------------------------------------------------
-- This plugin is required to intercept some Windows kernel functions.
-- Guest code patching monitors execution and transparently changes
-- the target program counter when it encounters a call instructions.

add_plugin("GuestCodeHooking")
pluginsConfig.GuestCodeHooking = {
  moduleNames = {}
}

{% for m in modules %}
    {% if m[1] %}
        -- Instrument kernel driver {{m[0]}} for fault injection
        table.insert(pluginsConfig.GuestCodeHooking["moduleNames"], "{{m[0]}}")
    {% endif %}
{% endfor %}


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

    -- Make this true if you want crash dumps.
    -- Note that crash dumps may be very large (100s of MBs)
    generateCrashDumpOnKernelCrash = false,
    generateCrashDumpOnUserCrash = false,

    -- Limit number of crashes we generate
    maxCrashDumps = 10,

    -- Uncompressed dumps have the same size as guest memory (e.g., 2GB),
    -- you almost always want to compress them.
    compressDumps = true
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

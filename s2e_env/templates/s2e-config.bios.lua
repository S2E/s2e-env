add_plugin("RawMonitor")
pluginsConfig.RawMonitor = {
    kernelStart=0xd0000,
    bios={
        name="bios",
        size=0x20000,
        start=0xd0000,
        nativebase=0xd0000,
        kernelmode=true
    }
}

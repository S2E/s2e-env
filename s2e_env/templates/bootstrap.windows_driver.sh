function make_seeds_symbolic {
    echo 1
}

# This function installs the driver. The target is the inf file.
#
# Notes:
#   - This function does not do anything else. It is up to you to customize it.
#     You can, e.g., call a program that makes use of the driver.
#   - You may also need to customize the driver installation in case the default
#     installer does not work with your driver, or if your driver comes with
#     a special installer.
#
function execute_target {
    local TARGET
    TARGET="$1"

    # Activate fault injection right before loading the driver
    ./drvctl.exe set_config FaultInjectionActive 1

    # Set this to 1 if you would like more aggressive error injection, to help harden your driver
    # against arbitrary API call errors. This may add false positives.
    # ./drvctl.exe set_config FaultInjectionOverapproximate 1

    # Ask windows to load the driver
    install_driver "$(win_path "$TARGET")"

    # TODO: you may need to manually start the driver using sc
    # sc start my_driver_service

    # TODO: you may want to download additional binaries with s2eget.exe (e.g., a test harness)
    # $S2EGET TestHarness.exe

    # Give some time for the driver to load.
    # You do not need this if your test harness knows when the driver is done loading.
    sleep 30
}

{% include 'bootstrap.windows_common.sh' %}

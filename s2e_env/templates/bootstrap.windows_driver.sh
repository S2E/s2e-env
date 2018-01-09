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
    install_driver "$(win_path "$1")"

    # TODO: you may need to manually start the driver using "sc start your_driver_service"
    # TODO: you may want to download additional binaries with s2eget.exe (e.g., a test driver)

    # Give some time for the driver to load
    sleep 30
}

{% include 'bootstrap.windows_common.sh' %}

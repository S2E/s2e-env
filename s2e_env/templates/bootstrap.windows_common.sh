function install_driver {
    local PREFIX
    local DRIVER
    DRIVER="$1"

    {% if image_arch=='x86_64' %}
    # The driver must be installed by a 64-bit process, otherwise
    # its files are copied into syswow64.
    # We use /c/Windows/sysnative to access 64-bit apps from 32-bit msys.
    PREFIX=/c/Windows/sysnative/
    {% else %}
    PREFIX=
    {% endif %}

    ${PREFIX}cmd.exe '\/c' "rundll32.exe setupapi,InstallHinfSection DefaultInstall 132 ${DRIVER}"
}

function target_init {
    # Start the s2e.sys WindowsMonitor driver
    install_driver 'c:\s2e\s2e.inf'
    sc start s2e

    # Create ram disk
    imdisk -a -s 2M -m X: -p "/fs:fat /q /y"
    drvctl.exe register_debug
    drvctl.exe wait
}

function target_tools {
    echo "s2e.sys s2e.inf drvctl.exe"
}

# This function converts an msys path into a Windows path
function win_path {
  local dir="$(dirname "$1")"
  local fn="$(basename "$1")"
  echo "$(cd "$dir"; echo "$(pwd -W)/$fn")" | sed 's|/|\\|g';
}

cd /c/s2e
S2EGET=./s2eget.exe
S2ECMD=./s2ecmd.exe
COMMON_TOOLS="s2ecmd.exe s2eget.exe s2eput.exe"

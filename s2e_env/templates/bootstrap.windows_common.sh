# In 64-bit mode, it is important to run commands using the 64-bit cmd.exe,
# otherwise most changes will be confined to the SysWow64 environment.
# This function takes care of calling the right cmd.exe depending on the guest OS.
function run_cmd {
    local PREFIX
    local CMD
    CMD="$1"

    {% if image_arch=='x86_64' %}
    # The driver must be installed by a 64-bit process, otherwise
    # its files are copied into syswow64.
    # We use /c/Windows/sysnative to access 64-bit apps from 32-bit msys.
    PREFIX=/c/Windows/sysnative/
    {% else %}
    PREFIX=
    {% endif %}

    ${PREFIX}cmd.exe '\/c' "${CMD}"
}

function install_driver {
    local PREFIX
    local DRIVER
    DRIVER="$1"

    run_cmd "rundll32.exe setupapi,InstallHinfSection DefaultInstall 132 ${DRIVER}"
}

function target_init {
    # Set FaultInjectionEnabled to 1 if you want to test a driver for proper error recovery
    # This only initializes fault injection infrastructure. Actual activation will be done
    # later when needed using drvctl.exe.
    run_cmd "reg add HKLM\\Software\\S2E /v FaultInjectionEnabled /t REG_DWORD /d {% if use_fault_injection %} 0x1 {% else %} 0 {% endif %} /f"

    # Start the s2e.sys WindowsMonitor driver
    install_driver 'c:\s2e\s2e.inf'
    sc start s2e

    # Create ram disk
    imdisk -a -s 2M -m X: -p "/fs:fat /q /y"
    drvctl.exe register_debug
    drvctl.exe wait
}

function target_tools {
    echo ""
}

# This function converts an msys path into a Windows path
function win_path {
  local dir="$(dirname "$1")"
  local fn="$(basename "$1")"
  echo "$(cd "$dir"; echo "$(pwd -W)/$fn")" | sed 's|/|\\|g';
}

S2ECMD=./s2ecmd.exe
S2EGET=./s2eget.exe
S2EPUT=./s2eput.exe
COMMON_TOOLS="s2ecmd.exe s2eget.exe s2eput.exe s2e.sys s2e.inf drvctl.exe"

function execute_target {
    local TARGET
    local SEED_FILE

    TARGET="$1"
    SEED_FILE="$2"

    if [ "x${SEED_FILE}" = "x" ]; then
        $CGCLOAD --enable-s2e ./${TARGET} > /tmp/out 2>&1
    else
        cat "${SEED_FILE}" | $CGCLOAD --enable-s2e --enable-seeds ./${TARGET} > /tmp/out 2>&1
    fi
}

function target_init {
    # Start the LinuxMonitor kernel module
    sudo modprobe s2e
}

function target_tools {
    echo "${TARGET_TOOLS32_ROOT}/cgcload"
}

S2ECMD=./s2ecmd
CGCLOAD="${TARGET_TOOLS32_ROOT}/cgcload"
COMMON_TOOLS="s2ecmd"

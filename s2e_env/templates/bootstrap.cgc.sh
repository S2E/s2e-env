# CGC has a different way of making seeds symbolic,
# override default behavior.
function make_seeds_symbolic {
    echo 0
}

function execute_target {
    local TARGET
    local SEED_FILE

    TARGET="$1"
    SEED_FILE="$2"

    if [ "x${SEED_FILE}" = "x" ]; then
        ./${TARGET} > /tmp/out 2>&1
    else
        # Make the seed file concolic and submit it to the cb-test application.
        # Note: CGC files don't need to be in a ram disk, as they will be made
        # symbolic at the syscall level. See DecreeMonitor for details.
        ${S2EGET} "${SEED_FILE}"
        ${CGCCMD} concolic on

        chmod +x ${SEED_FILE}
        cb-test --directory $(pwd) --xml ${SEED_FILE} --cb ${TARGET} --should_core --timeout 3600 2>&1
    fi
}

function target_init {
    # Patch cb-test so that it works without core dumps
    sudo sed -i 's/resource.RLIM_INFINITY/0/g' /usr/bin/cb-test

    # Some binaries have strange headers, allow them here
    echo 1 | sudo tee /proc/sys/cgc/relaxed_headers

    # Start the DecreeMonitor kernel module
    sudo modprobe s2e
}

function target_tools {
    echo "${TARGET_TOOLS_ROOT}/cgccmd"
}

S2ECMD=./s2ecmd
S2EGET=./s2eget
S2EPUT=./s2eput
COMMON_TOOLS="s2ecmd s2eget s2eput"

CGCCMD=${TARGET_TOOLS_ROOT}/cgccmd

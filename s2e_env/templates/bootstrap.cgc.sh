function execute_target {
    TARGET="$1"
    ./${TARGET} > /tmp/out 2>&1
}

function execute_target_with_seed {
    TARGET="$1"
    SEED_FILE="$2"

    # Make the seed file concolic and submit it to the cb-test application.
    # Note: CGC files don't need to be in a ram disk, as they will be made
    # symbolic at the syscall level. See DecreeMonitor for details.
    ./s2eget ${SEED_FILE}
    ./cgccmd concolic on

    chmod +x ${SEED_FILE}
    cb-test --directory $(pwd) --xml ${SEED_FILE} --cb ${TARGET} --should_core --timeout 3600 2>&1
}

function target_init {
    # Patch cb-test so that it works without core dumps
    sudo sed -i 's/resource.RLIM_INFINITY/0/g' /usr/bin/cb-test

    # Some binaries have strange headers, allow them here
    echo 1 | sudo tee /proc/sys/cgc/relaxed_headers
}

function target_tools {
    echo "cgccmd"
}

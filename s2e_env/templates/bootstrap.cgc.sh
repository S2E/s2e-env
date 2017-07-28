function execute_target {
    TARGET="$1"
    ./${TARGET} > /tmp/out 2>&1
}

{% if use_seeds %}
# Executes the target with a seed file as input.
# You can customize this function if you need to do special processing
# on the seeds, tweak arguments, etc.
function execute_target_with_seed {
    TARGET="$1"
    SEED_FILE="$2"

    # Make the seed file concolic and submit it to the cb-test application.
    # Note: CGC files don't need to be in a ram disk, as they will be made
    # symbolic at the syscall level. See DecreeMonitor for details.
    ${S2EGET} "${SEED_FILE}"
    ./cgccmd concolic on

    chmod +x ${SEED_FILE}
    cb-test --directory $(pwd) --xml ${SEED_FILE} --cb ${TARGET} --should_core --timeout 3600 2>&1
}
{% endif %}

function target_init {
    # Patch cb-test so that it works without core dumps
    sudo sed -i 's/resource.RLIM_INFINITY/0/g' /usr/bin/cb-test

    # Some binaries have strange headers, allow them here
    echo 1 | sudo tee /proc/sys/cgc/relaxed_headers

    # Start the DecreeMonitor kernel module
    sudo modprobe s2e
}

function target_tools {
    echo "cgccmd"
}

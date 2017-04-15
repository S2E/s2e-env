{% include 'bootstrap.header.sh' %}

# Execute the target
function execute {
    TARGET=$1

    # Make sure that the target is executable
    chmod +x ${TARGET}

    # Enable seeds and wait until a seed file is available. If you are not
    # using seeds then this loop will not affect symbolic execution - it will
    # simply never be scheduled
    ./s2ecmd seedsearcher_enable
    while true; do
        SEED_FILE=$(./s2ecmd get_seed_file)

        if [ $? -eq 255 ]; then
            # Avoid flooding the log with messages if we are the only runnable
            # state in the S2E instance
            sleep 1
            continue
        fi

        break
    done

    if [ -n "${SEED_FILE}" ]; then
        # Make the seed file concolic and submit it to the cb-test application
        ./s2eget ${SEED_FILE}
        ./cgccmd concolic on

        chmod +x ${SEED_FILE}
        cb-test --directory $(pwd) --xml ${SEED_FILE} --cb ${TARGET} --should_core --timeout 3600 2>&1
    else
        # If no seed file exists, just run the target
        ./${TARGET} > /tmp/out 2>&1
    fi
}

###############################################
# Bootstrap script starts executing from here #
###############################################

# Patch cb-test so that it works without core dumps
sudo sed -i 's/resource.RLIM_INFINITY/0/g' /usr/bin/cb-test

# Some binaries have strange headers, allow them here
echo 1 | sudo tee /proc/sys/cgc/relaxed_headers

update_guest_tools

{% include 'bootstrap.common.sh' %}

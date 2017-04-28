{% include 'bootstrap.header.sh' %}

# Execute the target
function execute {
    TARGET=$1

    # Make sure that the target is executable
    chmod +x ${TARGET}

    {% if use_symb_input_file == true %}
    # Create a symbolic file of size 256 bytes
    SYMB_FILE="/tmp/input"
    truncate -s 256 ${SYMB_FILE}

    if [ $? -ne 0 ]; then
        ./s2ecmd kill 1 "Failed to create symbolic file"
        exit 1
    fi

    ./s2ecmd symbfile ${SYMB_FILE}
    {% endif %}

    {% if dynamically_linked == true %}
    # {{ target }} is dynamically linked, so s2e.so has been preloaded to
    # provide symbolic arguments to the target if required. You can do so by
    # using the ``S2E_SYM_ARGS`` environment variable as required
    LD_PRELOAD=./s2e.so ./${TARGET} {{ target_args | join(' ') }}
    {% else %}
    ./${TARGET} {{ target_args | join(' ') }}
    {% endif %}
}

###############################################
# Bootstrap script starts executing from here #
###############################################

update_guest_tools

{% include 'bootstrap.common.sh' %}

# This function executes the target program.
# You can customize it if your program needs special invocation,
# custom symbolic arguments, etc.
function execute_target {
    local TARGET
    TARGET="$1"

    {% if use_symb_input_file %}
    SYMB_FILE="$(prepare_inputs)"
    {% endif %}

    {% if dynamically_linked == true %}
    # {{ target }} is dynamically linked, so s2e.so has been preloaded to
    # provide symbolic arguments to the target if required. You can do so by
    # using the ``S2E_SYM_ARGS`` environment variable as required
    S2E_SYM_ARGS="{{ sym_args | join(' ') }}" LD_PRELOAD=./s2e.so ./${TARGET} {{ target_args | join(' ') }} > /dev/null 2> /dev/null
    {% else %}
    ./${TARGET} {{ target_args | join(' ') }} > /dev/null 2> /dev/null
    {% endif %}
}

{% if use_seeds %}
# Executes the target with a seed file as input.
# You can customize this function if you need to do special processing
# on the seeds, tweak arguments, etc.
function execute_target_with_seed {
    local TARGET
    local SEED_FILE
    local SYMB_FILE

    TARGET="$1"
    SEED_FILE="$2"

    ${S2EGET} "${SEED_FILE}"

    SYMB_FILE="$(prepare_inputs ${SEED_FILE})"

    {% if dynamically_linked == true %}
    # {{ target }} is dynamically linked, so s2e.so has been preloaded to
    # provide symbolic arguments to the target if required. You can do so by
    # using the ``S2E_SYM_ARGS`` environment variable as required
    S2E_SYM_ARGS="{{ sym_args | join(' ') }}" LD_PRELOAD=./s2e.so ./${TARGET} {{ target_args | join(' ') }} > /dev/null 2> /dev/null
    {% else %}
    ./${TARGET} {{ target_args | join(' ') }} > /dev/null 2> /dev/null
    {% endif %}
}
{% endif %}

# Nothing more to initialize on Linux
function target_init {
    # Start the LinuxMonitor kernel module
    sudo modprobe s2e
}

# Returns Linux-specific tools
function target_tools {
    echo "s2e.so"
}

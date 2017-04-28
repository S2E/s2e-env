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
    LD_PRELOAD=./s2e.so ./${TARGET} {{ target_args | join(' ') }}
    {% else %}
    ./${TARGET} {{ target_args | join(' ') }} > /dev/null 2> /dev/null
    {% endif %}
}

# Executes the target with a seed file as input.
# You can customize this function if you need to do special processing
# on the seeds, tweak arguments, etc.
function execute_target_with_seed {
    local TARGET
    local SEED_FILE
    local SYMB_FILE

    TARGET="$1"
    SEED_FILE="$2"

    ./s2eget "${SEED_FILE}"

    SYMB_FILE="$(prepare_inputs \"$SEED_FILE\")"

    # Make the seed file concolic and submit it to the cb-test application
    ./${TARGET} {{ target_args | join(' ') }} > /dev/null 2> /dev/null
}

# Nothing more to initialize on Linux
function target_init {
    # Dummy instruction
    echo -n
}

# Returns Linux-specific tools
function target_tools {
    echo "s2e.so"
}

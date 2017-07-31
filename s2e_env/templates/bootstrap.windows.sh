# This function executes the target program.
# You can customize it if your program needs special invocation,
# custom symbolic arguments, etc.
function execute_target {
    local TARGET
    TARGET="$1"

    {% if use_symb_input_file %}
    SYMB_FILE="$(prepare_inputs)"
    {% endif %}

    ./${TARGET} {{ target_args | join(' ') }} > /dev/null 2> /dev/null
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

    ./${TARGET} {{ target_args | join(' ') }} > /dev/null 2> /dev/null
}
{% endif %}

{% include 'bootstrap.windows_common.sh' %}

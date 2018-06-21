function make_seeds_symbolic {
    echo 1
}

# This function executes the target program.
# You can customize it if your program needs special invocation,
# custom symbolic arguments, etc.
function execute_target {
    local TARGET
    local SYMB_FILE

    TARGET="$1"
    SYMB_FILE="$2"

    ./${TARGET} {{ target_args | join(' ') }} > /dev/null 2> /dev/null
}

{% include 'bootstrap.windows_common.sh' %}

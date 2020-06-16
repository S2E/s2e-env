function make_seeds_symbolic {
    echo 1
}

# This function executes the target program.
# You can customize it if your program needs special invocation,
# custom symbolic arguments, etc.
function execute_target {
    run_cmd "$@" > /dev/null 2> /dev/null
}

{% include 'bootstrap.windows_common.sh' %}

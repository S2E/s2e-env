# This function executes the target program.
# You can customize it if your program needs special invocation,
# custom symbolic arguments, etc.
function execute_target {
    local TARGET
    TARGET="$1"

    # The DLL entry point (i.e. the argument directly following the comma) and
    # its arguments can be modified here
    rundll32.exe ${TARGET},{{ target_args | join(' ') }}
}

{% include 'bootstrap.windows_common.sh' %}

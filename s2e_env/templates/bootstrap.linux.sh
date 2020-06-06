function make_seeds_symbolic {
    echo 1
}

# This function executes the target program.
# You can customize it if your program needs special invocation,
# custom symbolic arguments, etc.
function execute_target {
    local TARGET

    TARGET="$1"
    shift

    {% if target.arch =='x86_64' %}
    S2E_SO="${TARGET_TOOLS64_ROOT}/s2e.so"
    {% else %}
    S2E_SO="${TARGET_TOOLS32_ROOT}/s2e.so"
    {% endif %}

    {% if dynamically_linked == true %}
    # {{ target.name }} is dynamically linked, so s2e.so has been preloaded to
    # provide symbolic arguments to the target if required. You can do so by
    # using the ``S2E_SYM_ARGS`` environment variable as required
    S2E_SYM_ARGS="{{ sym_args | join(' ') }}" LD_PRELOAD="${S2E_SO}" "${TARGET}" "$@" > /dev/null 2> /dev/null
    {% else %}
    "${TARGET}" $* > /dev/null 2> /dev/null
    {% endif %}
}

# Nothing more to initialize on Linux
function target_init {
    # Start the LinuxMonitor kernel module
    sudo modprobe s2e
}

# Returns Linux-specific tools
function target_tools {
    {% if image_arch=='x86_64' %}
    echo "${TARGET_TOOLS32_ROOT}/s2e.so" "${TARGET_TOOLS64_ROOT}/s2e.so"
    {% else %}
    echo "${TARGET_TOOLS32_ROOT}/s2e.so"
    {% endif %}
}

S2ECMD=./s2ecmd
S2EGET=./s2eget
S2EPUT=./s2eput
COMMON_TOOLS="s2ecmd s2eget s2eput"

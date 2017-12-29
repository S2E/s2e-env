# This file must be used with "source install/bin/s2e_activate" *from bash*.
# You cannot run it directly

s2e_deactivate() {
    if ! [ -z "${_S2E_OLD_VIRTUAL_PS1+_}" ] ; then
        PS1="$_S2E_OLD_VIRTUAL_PS1"
        export PS1
        unset _S2E_OLD_VIRTUAL_PS1
    fi

    unset S2EDIR

    if [ ! "${1-}" = "nondestructive" ] ; then
        # Self destruct!
        unset -f s2e_deactivate
    fi
}

# unset irrelvant variables
s2e_deactivate nondestructive

S2EDIR="{{ S2EDIR }}"
export S2EDIR

if [ -z "${S2E_ENV_DISABLE_PROMPT-}" ] ; then
    _S2E_OLD_VIRTUAL_PS1="$PS1"
    if [ "x" != x ] ; then
        PS1="$PS1"
    else
        PS1="[S2E:`basename \"$S2EDIR\"`] $PS1"
    fi
    export PS1
fi

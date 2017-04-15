#!/bin/bash
#
# This file was automatically generated by s2e-env at
# {{ current_time | datetimefilter }}
#
# This script can be used to run the S2E analysis. Additional QEMU command line
# arguments can be passed to this script at run time
#

export S2E_CONFIG=s2e-config.lua
export S2E_SHARED_DIR={{ install_dir }}/share/libs2e
export S2E_MAX_PROCESSES=1

LD_PRELOAD={{ install_dir }}/share/libs2e/libs2e-{{ arch }}-s2e.so      \
    {{ install_dir }}/bin/qemu-system-{{ arch }}                        \
    -k en-us -nographic -monitor null -m {{ memory }} -enable-kvm   \
    -drive file={{ image_path }},format=s2e,cache=writeback         \
    -serial file:serial.txt {{ qemu_extra_flags }}          \
    -loadvm {{ snapshot }} $*

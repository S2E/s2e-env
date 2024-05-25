#!/bin/sh

# This script verifies that the generated POVs actually work.

set -xe

ENV_DIR="{{ env_dir }}"
INSTALL_DIR="$ENV_DIR/install"
GUEST_TOOLS32="${ENV_DIR}/install/bin/guest-tools32"

CFLAGS="-L${GUEST_TOOLS32}/lib -I${ENV_DIR}/source/s2e/guest/linux/include"

for v in s2e-last/*.c; do
    echo "======= CHECKING POV $v ======="
    DIR="$(dirname $v)"
    POV="$(basename $v .c)"
    gcc -O0 -g -m32 -o "$DIR/$POV" $CFLAGS "$v" -lpov -lcgc
    $GUEST_TOOLS32/povtest "--pov=$DIR/${POV}" -- $GUEST_TOOLS32/cgcload {{ target.path }}
done

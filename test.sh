#!/bin/bash
# Copyright (c) 2018-2020 Cyberhaven
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# This script creates a test venv in the current directory, installs s2e-env there,
# checks code style and tests it.
#
# Set SRC_DIR to the location that contains s2e-env in case you run this script from a different directory.

set -ex

SRC_DIR=${SRC_DIR:-.}

python3 -m venv venv-test
. venv-test/bin/activate
pip install --upgrade pip

pip install "$SRC_DIR"
pip install pylint pytest-cov mock

echo Running pylint...
pylint -rn --rcfile=${SRC_DIR}/pylint_rc ${SRC_DIR}/s2e_env

echo Running tests...
export TERM=linux
export TERMINFO=/etc/terminfo

# Patch buggy pwnlib
sed -i "s/file('\/dev\/null', 'r')\.fileno()/os\.open\(os\.devnull, os\.O_RDONLY)/g" \
    venv-test/lib/python*/site-packages/pwnlib/term/key.py

pytest --cov=${SRC_DIR}/s2e_env --cov-report=html ${SRC_DIR}/tests/

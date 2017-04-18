"""
MIT License

Copyright (c) 2017 Dependable Systems Laboratory, EPFL

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


import sys

import termcolor


def print_info(msg):
    """
    Print an info message to stdout.
    """
    text = 'INFO: %s\n' % msg
    sys.stdout.write(text)


def print_success(msg):
    """
    Print a success message to stdout.
    """
    text = termcolor.colored('INFO: %s\n' % msg, 'green')
    sys.stdout.write(text)


def print_warn(msg):
    """
    Print a warning message to stdout.
    """
    text = termcolor.colored('WARN: %s\n' % msg, 'yellow')
    sys.stdout.write(text)


def print_error(msg):
    """
    Print an error message to stderr.
    """
    text = termcolor.colored('ERROR: %s\n' % msg, 'red')
    sys.stderr.write(text)

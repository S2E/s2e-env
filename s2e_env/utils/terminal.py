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

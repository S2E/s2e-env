"""
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


import logging
import os
import termcolor


# Success log level
SUCCESS = 25


def configure_logging(level=logging.INFO, use_color=True):
    """
    Configure te global logging settings.
    """

    override_level = os.environ.get('S2EENV_LOG_LEVEL', None)
    if override_level:
        level = logging.getLevelName(override_level)

    # Add a 'SUCCESS' level to the logger
    logging.addLevelName(SUCCESS, 'SUCCESS')
    logging.Logger.success = success

    # Configure colored logging
    logger = logging.getLogger()
    logger.setLevel(level)

    # Overwrite any existing handlers
    if logger.handlers:
        logger.handlers = []

    colored_handler = logging.StreamHandler()
    colored_handler.setFormatter(ColoredFormatter(use_color=use_color))
    logger.addHandler(colored_handler)


# pylint: disable=protected-access
def success(self, msg, *args, **kwargs):
    if self.isEnabledFor(SUCCESS):
        self._log(SUCCESS, msg, args, **kwargs)


def log_to_file(log_file):
    """
    Switches logging to a file.
    The file contains color codes and can be viewed with less -r.
    """
    fileh = logging.FileHandler(log_file, 'w')
    fileh.setFormatter(ColoredFormatter())

    # Reset the root logger in order to replace the default console one
    log = logging.getLogger()
    for hdlr in log.handlers:
        log.removeHandler(hdlr)
    log.addHandler(fileh)


class ColoredFormatter(logging.Formatter):
    """
    Prints log messages in color.
    """

    # Maps log levels to colors
    LOG_COLOR_MAP = {
        'WARNING': 'yellow',
        'ERROR': 'red',
        'SUCCESS': 'green',
    }

    def __init__(self, use_color=True):
        super(ColoredFormatter, self).__init__(\
            fmt='%(levelname)s: [%(name)s] %(message)s')

        self._use_color = use_color

    def format(self, record):
        if self._use_color:
            color = ColoredFormatter.LOG_COLOR_MAP.get(record.levelname)

            if color:
                record.levelname = termcolor.colored(record.levelname, color)
                record.name = termcolor.colored(record.name, color)
                record.msg = termcolor.colored(record.msg, color)

        return super(ColoredFormatter, self).format(record)

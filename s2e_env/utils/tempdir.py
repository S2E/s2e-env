from __future__ import print_function

import shutil
import sys
import tempfile
import warnings


# Adapted from http://stackoverflow.com/a/19299884/5894531
class TemporaryDirectory(object):
    """
    Create and return a temporary directory.  This has the same behavior as
    mkdtemp but can be used as a context manager. For example:

        with TemporaryDirectory() as tmpdir:
            ...

    Upon exiting the context, the directory and everything contained in it are
    removed.
    """

    _warn = warnings.warn

    def __init__(self, suffix='', prefix='tmp', dir_=None):
        self._closed = False
        self.name = None
        self.name = tempfile.mkdtemp(suffix, prefix, dir_)

    def __repr__(self):
        return "<{} {!r}>".format(self.__class__.__name__, self.name)

    def __enter__(self):
        return self.name

    def __exit__(self, exc, value, tb):
        self.cleanup()

    def __del__(self):
        self.cleanup(warn=True)

    def cleanup(self, warn=False):
        if self.name and not self._closed:
            try:
                shutil.rmtree(self.name)
            except Exception as e:
                print('ERROR: {!r} while cleaning up {!r}'.format(e, self),
                      file=sys.stderr)
                return

            self._closed = True
            if warn:
                self._warn('Implicitly cleaning up {!r}'.format(self),
                           RuntimeWarning)

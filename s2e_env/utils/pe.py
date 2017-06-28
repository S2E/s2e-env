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


import pefile


class PEAnalysis(object):
    """
    Support class for doing some simple static analysis on PE files.
    """

    def __init__(self, pe_path):
        self._pe_path = pe_path
        self._pe = None

    def __enter__(self):
        self._pe = pefile.PE(self._pe_path)

        return self

    def __exit__(self, exec_type, exec_value, traceback):
        if self._pe:
            self._pe.close()

    def get_exports(self):
        """
        Get a list of exported symbols from the PE file.

        Returns:
            A list of exported symbol names. If a symbol name is not available,
            the ordinal number is used instead.
        """
        exports = []

        for export in self._pe.DIRECTORY_ENTRY_EXPORT.symbols:
            if export.name:
                exports.append(export.name)
            else:
                export.append('%d' % export.ordinal)

        return exports

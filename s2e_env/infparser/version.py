"""
Copyright (c) 2013-2014 Dependable Systems Laboratory, EPFL
Copyright (c) 2018 Cyberhaven

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


class InfVersion:
    """
    This class represents version information.
    Driver inf files encode it as follows:

        nt[Architecture][.[OSMajorVersion][.[OSMinorVersion][.[ProductType][.SuiteMask]]]]
    """

    def __init__(self, version):
        self.architecture = None
        self.major = None
        self.minor = None
        self.product_type = None
        self.suite_mask = None

        if version is None:
            return

        version = str(version.lower())
        if not version.startswith('nt'):
            return

        # Fields can be empty...
        v = version.split('.')
        if len(v) >= 1:
            self.architecture = v[0] if v[0] else None
        if len(v) >= 2:
            self.major = int(v[1]) if v[1] else None
        if len(v) >= 3:
            self.minor = int(v[2]) if v[2] else None
        if len(v) >= 4:
            self.product_type = int(v[3], 16) if v[3] else None
        if len(v) >= 5:
            self.suite_mask = int(v[4], 16) if v[4] else None

        # Normalize the arch
        if self.architecture == 'ntx86':
            self.architecture = 'nt'

    def matches(self, desired_version):
        if self.architecture and desired_version.architecture:
            if desired_version.architecture != self.architecture:
                return False

        v = (self.major, self.minor)
        dv = (desired_version.major, desired_version.minor)

        # A given OS version can support drivers for previous versions but not for later
        if v[0] is not None and v[1] is not None and dv[0] is not None and dv[1] is not None:
            if dv < v:
                return False

        # No minor version, compare the major one
        if v[1] is None or dv[1] is None:
            if v[0] is not None and dv[0] is not None:
                if v[0] < dv[0]:
                    return False

        return True

    def __str__(self):
        if self.architecture is None:
            return 'Windows 2000 and later'

        ret = '%s' % self.architecture

        if self.major is not None:
            ret += ' %d' % self.major
            if self.minor is not None:
                ret += '.%d' % self.minor

        return ret

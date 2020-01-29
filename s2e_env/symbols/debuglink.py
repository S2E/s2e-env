"""
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

import binascii
import logging
import os
import struct

from elftools.elf.elffile import ELFFile

logger = logging.getLogger('debuglink')


def get_build_id(path):
    """
    Return the build-id encoded in the .note.gnu.build-id section
    """
    with open(path, 'rb') as f:
        elf = ELFFile(f)
        section = elf.get_section_by_name('.note.gnu.build-id')
        data = section.data()
        name_size, hash_size, identifier = struct.unpack('<III', data[:12])
        name, info_hash = struct.unpack('<%ds%ds' % (name_size, hash_size), data[12:])

        hexval = binascii.hexlify(info_hash)
        logger.debug('%s: id=%s name=%s hash=%s (%d)', path, identifier, name, hexval, len(info_hash))

        return os.path.join('.build-id', hexval[0:2], '%s.debug' % hexval[2:])


def get_debug_file_for_binary(path):
    """
    On Linux, large binaries may have their debug info stripped and placed into a separate file.
    This function returns the debug file that is associated with the given binary.
    """
    build_id = get_build_id(path)
    ret = os.path.join('usr', 'lib', 'debug', build_id)
    logger.debug('Computed debug file: %s', ret)
    return ret

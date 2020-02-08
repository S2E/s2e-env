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

# TODO: implement line continuator
# TODO: support semicolons in quoted strings

import codecs
import logging
import re

from .case_insensitive_dict import CaseInsensitiveDict
from .section import InfSection

logger = logging.getLogger('infparser')

SECTION_PATTERN = re.compile(r'\[(.+)\]')


class InfFileParser:
    def __init__(self):
        self._sections = CaseInsensitiveDict()

    @staticmethod
    def _read_file(filename):
        decoded = False

        for codec in ('utf-16', 'utf-8'):
            try:
                with codecs.open(filename, 'r', codec) as fp:
                    data = fp.read()
                    decoded = True
            except UnicodeError:
                pass

        if not decoded:
            raise Exception('Could not decode %s' % (filename))

        return data

    @staticmethod
    def parse(filename):
        data = InfFileParser._read_file(filename)
        return InfFileParser.parse_string(data)

    @staticmethod
    def _decode(s, encodings=('ascii', 'utf8', 'utf16')):
        for encoding in encodings:
            try:
                return s.decode(encoding)
            except UnicodeDecodeError:
                pass
            except UnicodeEncodeError:
                pass

        return s.decode('ascii', 'ignore')

    @staticmethod
    def parse_string(input_string):
        if not isinstance(input_string, str):
            input_string = InfFileParser._decode(input_string)

        input_string = input_string.split('\n')
        current_section = InfSection('')
        sections = CaseInsensitiveDict()

        for line in input_string:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line[0] == ';':
                continue

            # Remove comment from line
            # TODO: does not work if semicolon is inside a quoted string
            data = line.split(';')
            line = data[0].strip()

            # Look for section name
            m = SECTION_PATTERN.search(line)
            if m:
                section_name = m.group(1)
                if current_section.name:
                    sections[current_section.name] = current_section
                current_section = InfSection(section_name)
                continue

            # Skip
            if not current_section.name:
                continue

            # The line is of the form key=value
            key_value = line.split('=')
            key = ''
            value = ''
            if len(key_value) >= 1:
                key = key_value[0].strip()
                if len(key) >= 2 and key[0] == '"':
                    key = key[1:-1]

            if len(key_value) >= 2:
                value = key_value[1].strip()
                if len(value) >= 2 and value[0] == '"':
                    value = value[1:-1]

            current_section.data[key] = value

        # Add the final section
        if current_section.name:
            sections[current_section.name] = current_section

        return sections

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

import logging
import re

from .case_insensitive_dict import CaseInsensitiveDict
from .device import Device, InstallInfo
from .parser import InfFileParser

logger = logging.getLogger('infparser')

MACRO_PATTERN = re.compile(r'(%.+%)')


class InfFile:
    def __init__(self, filename):
        self._filename = filename
        self._sections = {}

    @staticmethod
    def from_file(filename):
        ret = InfFile(filename)

        # pylint: disable=protected-access
        ret._sections = InfFileParser.parse(filename)
        return ret

    @staticmethod
    def from_string(input_string):
        ret = InfFile('noname.inf')

        # pylint: disable=protected-access
        ret._sections = InfFileParser.parse_string(input_string)
        return ret

    @staticmethod
    def _is_string_key(string_spec):
        return string_spec[0] == '%' and string_spec[len(string_spec) - 1] == '%'

    @staticmethod
    def to_string_key(string_spec):
        k = string_spec.split('%')
        return k[1]

    def get_string(self, key):
        # If the INF file is broken and doesn't define the string for the key,
        # just treat the key as a string.
        if not self._is_string_key(key):
            return key

        string_key = self.to_string_key(key)
        if string_key not in self._sections['strings'].data:
            return ''

        return self._sections['strings'].data[string_key]

    # Key can contain one or more %xxx% string tokens
    # E.g. %NVidia% Quadro2 Pro
    def expand_key(self, key):
        # List of string tokens to expand
        tokens_found = []

        for m in MACRO_PATTERN.finditer(key):
            tokens_found.append(m.group(1))

        for m in tokens_found:
            expanded = self.get_string(m)
            key = key.replace(m, expanded)

        return key

    def has_manufacturers(self):
        return 'manufacturer' in self._sections

    def get_class(self):
        try:
            return self._sections['version'].data['class']
        except KeyError:
            return None

    def get_catalog(self):
        try:
            return self._sections['version'].data['catalogfile']
        except KeyError:
            return None

    # Return a map mfgid=>[(mfgname, version)...]
    # If no version, the entry contains (mfgname, None)
    # [Manufacturer]
    # manufacturer-identifier
    # [manufacturer-identifier]
    # [manufacturer-identifier]
    # ...
    # manufacturer-name |
    # %strkey%=models-section-name |
    # %strkey%=models-section-name [,TargetOSVersion] [,TargetOSVersion] ...
    def get_manufacturers(self):
        ret = CaseInsensitiveDict()
        if not self.has_manufacturers():
            return ret

        mfg = self._sections['manufacturer']

        # For each manufacturer...
        for mfg_key in mfg.data.keys():
            # The key is the string identifier,
            # the value is the section that defines the manufacturer
            manufacturer = mfg_key
            if self._is_string_key(mfg_key):
                manufacturer = self.get_string(mfg_key)
                if not manufacturer:
                    continue

            if not manufacturer.strip():
                logger.warning('Empty manufacturer string %s', manufacturer)

            # Parse the multiple versions
            models_section = mfg.data[mfg_key].split(',')

            if len(models_section) == 1:
                ret[manufacturer] = [(models_section[0], None)]
                continue

            versions = []
            for version in models_section[1:]:
                versions.append((models_section[0], version.strip()))

            # Append the empty version for Win2K drivers
            if models_section[0] in self._sections:
                versions.append((models_section[0], None))

            ret[manufacturer] = versions

        return ret

    # mfgKey is the section id containing the list of models for
    # that manufacturer. The key may come with additional version info.
    # [models-section-name] |
    # [models-section-name.TargetOSVersion]  (Windows XP and later versions of Windows)
    # device-description=install-section-name[,hw-id][,compatible-id...]
    # [device-description=install-section-name[,hw-id][,compatible-id]...] ...
    #
    # Returns a mapping from the device key to the actual device
    def get_models(self, dev_key, version):
        ret = CaseInsensitiveDict()

        if version:
            dev_key = '%s.%s' % (dev_key, version)

        if dev_key not in self._sections:
            logger.warning('No section for %s', dev_key)
            return ret

        devices = self._sections[dev_key]
        for k in devices.data.keys():
            device_name = self.expand_key(k)
            install_section = ''
            hardware_id = ''

            # device-description=install-section-name[,hw-id][,compatible-id...]
            descriptors = devices.data[k].split(',')
            if len(descriptors) >= 1:
                install_section = descriptors[0].strip()
            if len(descriptors) >= 2:
                hardware_id = descriptors[1].strip()

            device = Device.create(device_name, install_section, hardware_id, version)
            device.installInfo = self.get_install_info(install_section)
            ret[k] = device

        return ret

    # Get install section info
    # The key may be a prefix, the final sections may have version suffixes
    # [install-section-name.Services] |
    # [install-section-name.nt.Services] |
    # [install-section-name.ntx86.Services] |
    # [install-section-name.ntia64.Services] |  (Windows XP and later versions of Windows)
    # [install-section-name.ntamd64.Services]  (Windows XP and later versions of Windows)
    def get_install_info(self, install_section_key):
        ret = dict()

        if not self._sections.prefixed_keys(install_section_key):
            logger.warning('Section %s does not exist', install_section_key)
            return ret

        for fk in self._sections.prefixed_keys(install_section_key):
            # Get the files to copy
            install_section = self._sections[fk].data
            install_info = InstallInfo()

            # Remove the potential suffix
            for ver in ('.nt', '.ntx86', '.ntia64', '.ntamd64'):
                if ver in fk:
                    install_info.version = ver[1:]

            # CopyFiles=@filename | file-list-section[,file-list-section] ...
            if 'copyfiles' in install_section:
                v = install_section['copyfiles']
                components = v.split(',')
                for s in components:
                    install_info.copyFiles |= self.get_files(s.strip())

            ret[fk] = install_info

        return ret

    # [file-list-section]
    # destination-file-name[,[source-file-name][,[unused][,flag]]]
    def get_files(self, file_list_section_key):
        ret = set()

        if file_list_section_key[0:1] == '@':
            ret.add(file_list_section_key[1:])
            return ret

        if file_list_section_key not in self._sections:
            logger.warning('File list section %s does not exist', file_list_section_key)
            return ret

        for f in self._sections[file_list_section_key].data.keys():
            components = f.split(',')
            ret.add(self.expand_key(components[0].lower()))

        return ret

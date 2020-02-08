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


class Device:
    def __init__(self, name, install_section, hardware_id):
        self.name = name
        self.install_section = install_section
        self.install_info = None
        self.hardware_id = hardware_id
        self.version = None

    @staticmethod
    def create(name, install_section, hardware_id, version):
        enumerator = hardware_id.split('\\')

        if len(enumerator) < 2:
            ret = Device(name, install_section, hardware_id)
        elif 'PCI' in enumerator[0]:
            ret = PCIDevice(name, install_section, hardware_id)
        elif 'USB' in enumerator[0]:
            ret = USBDevice(name, install_section, hardware_id)
        else:
            ret = Device(name, install_section, hardware_id)

        ret.version = version
        return ret

    # pylint: disable=no-self-use
    def get_s2e_cfg(self):
        raise Exception('Not implemented')

    def is_pci(self):
        return isinstance(self, PCIDevice)

    def __unicode__(self):
        return 'DEVICE %s %s [%s]' % (self.install_section, self.hardware_id, self.name)

    def __str__(self):
        return str(self).encode('utf-8')


class PCIDevice(Device):
    def __init__(self, name, install_section, hardware_id):
        super(PCIDevice, self).__init__(name, install_section, hardware_id)

        if hardware_id.startswith('"') and hardware_id.endswith('"'):
            hardware_id = hardware_id[1:-1]

        enumerator = hardware_id.split('\\')
        pci_desc = enumerator[1].split('&')
        self.vendorId = 0
        self.deviceId = 0
        self.subsystemId = 0
        self.revisionId = 0

        for f in pci_desc:
            if 'VEN_' in f:
                self.vendorId = int(f.split('VEN_')[1], 16)
            if 'DEV_' in f:
                self.deviceId = int(f.split('DEV_')[1], 16)
            if 'SUBSYS_' in f:
                self.subsystemId = int(f.split('SUBSYS_')[1], 16)
            if 'REV_' in f:
                self.revisionId = int(f.split('REV_')[1], 16)

    def get_s2e_cfg(self):
        return {
            'name': self.name,
            'vid': self.vendorId,
            'pid': self.deviceId,
            'revId': self.revisionId,
            'hwId': self.hardware_id,
            'ssid': self.subsystemId >> 16,
            'ssvid': self.subsystemId & 0xffff,
        }

    def __unicode__(self):
        return 'DEVICE PCI VID=%x PID=%x SUBSYS=%x [%s] %s %s %s' % (
            self.vendorId, self.deviceId, self.subsystemId,
            self.name, self.hardware_id, self.install_section, self.version
        )


class USBDevice(Device):
    def __init__(self, name, install_section, hardware_id):
        super(USBDevice, self).__init__(name, install_section, hardware_id)
        enumerator = hardware_id.split('\\')
        desc = enumerator[1].split('&')
        self.vendorId = 0
        self.deviceId = 0
        self.subsystemId = 0

        for f in desc:
            if 'VID_' in f:
                self.vendorId = int(f.split('VID_')[1], 16)
            if 'PID_' in f:
                self.deviceId = int(f.split('PID_')[1], 16)

    def __unicode__(self):
        return 'DEVICE USB VID=%x PID=%x [%s]' % (self.vendorId, self.deviceId, self.name)


class InstallInfo:
    def __init__(self):
        self.copyFiles = set()
        self.version = None

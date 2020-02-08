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

from .file import InfFile

logger = logging.getLogger('infparser')


class Driver:
    def __init__(self, filename):
        self._filename = filename
        self._all_files = set()
        self._all_manufacturers = set()

    def analyze(self):
        inf_file = InfFile.from_file(self._filename)

        logger.info('%s', self._filename)
        logger.info('  class: %s catalog: %s', inf_file.get_class(), inf_file.get_catalog())

        catalog = inf_file.get_catalog()
        if catalog:
            self._all_files.add(catalog)

        manufacturers = inf_file.get_manufacturers()

        for k in manufacturers.keys():
            logger.info('  %s = %s', k, manufacturers[k])
            for version in manufacturers[k]:
                logger.info('  version: %s', version)
                devices = inf_file.get_models(version[0], version[1])
                drv_files = set()
                for dk in devices.keys():
                    for ver in devices[dk].installInfo.keys():
                        drv_files |= devices[dk].installInfo[ver].copyFiles

                        logger.info('    %s %s', devices[dk], drv_files)
                    self._all_files |= drv_files

        for m in inf_file.get_manufacturers().keys():
            self._all_manufacturers.add(m)

        default_install = inf_file.get_install_info('DefaultInstall')
        for value in default_install.values():
            self._all_files |= value.copyFiles

    def get_files(self):
        return self._all_files

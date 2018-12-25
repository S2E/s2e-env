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


import os

from setuptools import setup, find_packages


setup(
    name='s2e-env',
    description='A command-line tool for administering S2E environments',
    long_description=open('README.md', 'r').read(),
    author='Adrian Herrera',
    author_email='adrian.herrera@epfl.ch',
    version=open(os.path.join('s2e_env', 'dat', 'VERSION'), 'r').read().strip(),
    url='http://s2e.systems',
    download_url='https://github.com/S2E/s2e-env.git',
    install_requires=[
        # S2E engine requirements
        'docutils',
        'pygments',

        # s2e-env requirements
        'enum34',
        'jinja2',
        'pefile',
        'psutil',
        'pyelftools==0.24+s2e',
        'python-magic',
        'pyyaml',
        'requests',
        'sh',
        'termcolor',
        'pytrie',
        'pwntools==3.12.0'
    ],
    tests_require=[
        'mock',
    ],
    packages=find_packages(),
    dependency_links=[
        'git+https://github.com/S2E/pyelftools.git#egg=pyelftools-0.24+s2e',
    ],
    include_package_data=True,
    package_data={
        's2e_env': [
            'templates/*',
            'dat/*',
        ],
    },
    entry_points={
        'console_scripts': [
            's2e = s2e_env.manage:main',
        ]
    },
    classifiers=[
        'Intended Audience :: Developers',
        'Environment :: Console',
        'Programming Language :: Python',
        'Topic :: Security',
        'Topic :: Software Development',
        'Topic :: System',
    ],
)

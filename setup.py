import os

from setuptools import setup, find_packages


setup(
    name='s2e-env',
    description='A command-line tool for administering S2E environments',
    long_description=open('README.md', 'r').read(),
    author='Adrian Herrera',
    author_email='adrian.herrera@epfl.ch',
    version=open(os.path.join('s2e_env', 'dat', 'VERSION'), 'r').read().strip(),
    url='http://s2e.epfl.ch',
    download_url='https://github.com/S2E/s2e-env.git',
    install_requires=[
        # S2E engine requirements
        'docutils',
        'pygments',

        # s2e-env requirements
        'jinja2',
        'psutil',
        'pyelftools',
        'python-magic',
        'pyyaml',
        'requests',
        'sh',
        'termcolor',
    ],
    packages=find_packages(),
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

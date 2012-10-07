#!/usr/bin/env python
import os
import re
from setuptools import setup

__doc__="""
Command-line password manager
"""

install_requires = []
try:
    import argparse
except:
    install_requires.append('argparse')

version = '0.0.1'

setup(name='sdb',
    version=version,
    description=__doc__,
    author='Gavin Wahl',
    author_email='gavinwahl@gmail.com',
    long_description=__doc__,
    packages=['sdb'],
    scripts=['sdb/sdb'],
    platforms = "any",
    license='BSD',
    test_suite='nose.collector',
    install_requires=install_requires,
    tests_require = ['nose', 'pytest'] + install_requires,
)

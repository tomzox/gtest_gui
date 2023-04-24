#!/usr/bin/env python3

#from distutils.core import setup
from setuptools import setup
import os
import subprocess
import sys

if os.path.exists('doc/pod2help.py'):
    proc_rst = subprocess.run(['doc/pod2help.py', "-rst", 'doc/gtest_gui.pod'],
                              stdout=subprocess.PIPE, text=True, check=True)
    long_description = proc_rst.stdout
else:
    long_description = None

setup(
    name='mote-gtest-gui',
    version='0.8.1',
    packages=['gtest_gui'],
    scripts=['bin/gtest_gui'],

    install_requires=['trowser'],

    author='T. Zoerner',
    author_email='tomzox@gmail.com',

    url='https://github.com/tomzox/gtest_gui',

    description="Module tester's Gtest GUI is a full-featured graphical user-interface " \
                "to C++ test applications using the GoogleTest framework.",

    long_description=long_description,
    long_description_content_type='text/x-rst',

    classifiers=[
          'Topic :: Software Development :: Testing',
          'Development Status :: 5 - Production/Stable',
          'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
          'Programming Language :: Python :: 3',
          'Operating System :: POSIX',
          'Operating System :: Microsoft :: Windows',
          'Environment :: X11 Applications',
          'Environment :: Win32 (MS Windows)',
          'Intended Audience :: Developers',
          ],
    keywords=['google-test', 'gtest', 'testing-tools', 'test-runners', 'tkinter', 'GUI'],
    platforms=['posix', 'win32'],
)

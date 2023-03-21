#!/usr/bin/env python3

# ------------------------------------------------------------------------ #
# Copyright (C) 2023 Th. Zoerner
# ------------------------------------------------------------------------ #
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# ------------------------------------------------------------------------ #

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

trowser_path = os.path.join(os.path.dirname(__file__), "trowser")
os_path = os.environ.get("PATH", None)
if os_path:
    os.environ["PATH"] = os_path + os.pathsep + trowser_path
else:
    os.environ["PATH"] = trowser_path

import gtest_gui.__main__

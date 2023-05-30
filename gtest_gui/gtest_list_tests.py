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

"""
Implements function gtest_list_tests for querying the GTest test case list.
"""

import re
import subprocess

from tkinter import messagebox as tk_messagebox
import gtest_gui.tk_utils as tk_utils
import gtest_gui.test_db as test_db
import gtest_gui.fcntl


def gtest_list_tests(pattern="", exe_file=None):
    """
    Query the given executable for the list of test case names via option
    "--gtest_list_tests".
    """
    if exe_file is None:
        exe_file = test_db.test_exe_name
    cmd = [exe_file, "--gtest_list_tests"]
    if pattern:
        cmd.append("--gtest_filter=" + pattern)
    try:
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True,
                              creationflags=gtest_gui.fcntl.subprocess_creationflags()) as proc:
            result = proc.communicate(timeout=10)
            if proc.returncode == 0:
                tc_names = _gtest_parse_test_list(result[0].rstrip())
                if not tc_names:
                    msg = ('Read empty test case list from executable "--gtest_list_tests". '
                           'Continue anyway?')
                    if not tk_messagebox.askokcancel(parent=tk_utils.tk_top, message=msg):
                        return None
                return tc_names

            msg = ("Gtest exited with error code %d when querying test case list: "
                   % proc.returncode) + str(result[1].rstrip())
            tk_messagebox.showerror(parent=tk_utils.tk_top, message=msg)
            return None

    except OSError as exc:
        msg = "Failed to read test case list: " + str(exc)
        tk_messagebox.showerror(parent=tk_utils.tk_top, message=msg)
        return None


def _gtest_parse_test_list(lines):
    tc_names = []
    tc_suite = ""
    for line in lines.split("\n"):
        match = re.match(r"^([^0-9\s]\S+\.)$", line)
        if match:
            tc_suite = match.group(1)
        elif tc_suite:
            match = re.match(r"^\s+([^0-9\s]\S+)$", line)
            if match:
                tc_name = tc_suite + match.group(1)
                tc_names.append(tc_name)
            else:
                tc_suite = ""
    return tc_names

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
from tkinter import messagebox as tk_messagebox
import tkinter as tk

import gtest_gui.config_db as config_db
import gtest_gui.dlg_main as dlg_main
import gtest_gui.dlg_config as dlg_config
import gtest_gui.gtest as gtest
import gtest_gui.test_db as test_db
import gtest_gui.tk_utils as tk_utils


def parse_argv_error(tk_top, msg, with_usage=True):
    if msg[-1] != "\n":
        msg += "\n"
    if with_usage:
        msg += "Usage: %s {[-trace] file}* [executable]" % sys.argv[0]

    if (os.name == "posix"):
        print(msg, file=sys.stderr)
    else:
        tk_messagebox.showerror(parent=tk_top, message=msg)

    sys.exit(1)


def parse_argv(tk_top):
    exe_name = ""
    trace_files = []
    next_is_trace = False
    for file_name in sys.argv[1:]:
        if file_name.startswith("-trace"):
            next_is_trace = True
            continue
        elif file_name.startswith("-"):
            parse_argv_error(tk_top, "Unknown command line option: %s" % file_name)

        try:
            st = os.stat(file_name)
        except OSError as e:
            # Note the file name is already included in the exception text
            parse_argv_error(tk_top, "Failed to access file: %s" % str(e), False)

        if (os.name == "posix"):
            is_exe = os.access(file_name, os.X_OK)
        else:
            is_exe = os.path.splitext(file_name)[1] == ".exe"

        if is_exe and not next_is_trace:
            if exe_name:
                parse_argv_error(tk_top, "More than one executable on the command line: %s" % file_name)
            exe_name = file_name
        else:
            trace_files.append(file_name)

        next_is_trace = False

    return (exe_name, trace_files)


# ----------------------------------------------------------------------------

def main():
    try:
        tk_top = tk.Tk(className="gtest_gui")
        tk_top.wm_withdraw()
        tk_top.wm_title("GtestGui")
    except Exception as e:
        print("Tk initialization failed: " + str(e), file=sys.stderr)
        sys.exit(1)

    exe_name, trace_files = parse_argv(tk_top)

    tk_utils.initialize(tk_top)
    gtest.initialize()

    config_db.rc_file_load()

    if config_db.options["startup_import_trace"]:
        if config_db.options["trace_dir"] and not os.path.exists(config_db.options["trace_dir"]):
            answer = tk_messagebox.showwarning(
                parent=tk_top, type="okcancel",
                message="Warning: Configured trace directory does not exist. Please check configuration.")
            if answer == "ok":
                dlg_config.create_dialog(tk_top)
        else:
            gtest.gtest_automatic_import()

    for file_name in trace_files:
        try:
            gtest.gtest_import_result_file(file_name, False)
        except OSError as e:
            msg = "Failed to import %s: %s" % (file_name, str(e))
            tk_messagebox.showerror(parent=tk_top, message=msg)
            sys.exit(1)

    global wid_main
    wid_main = dlg_main.Main_window(tk_top, exe_name)

    tk_top.wm_deiconify()

    try:
        tk_top.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()

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

import errno
from datetime import datetime
import json
import os
import re
import sys
import tempfile
from tkinter import messagebox as tk_messagebox

import gtest_gui.tk_utils as tk_utils

# Options set via configuration menu
options = {
    "browser": "trowser.py",
    "browser_stdin": True,
    "seed_regexp": "",
    "trace_dir": "",
    "exit_clean_trace": True,
    "startup_import_trace": True,
    "copy_executable": True,
    "valgrind1": "valgrind --leak-check=full --show-leak-kinds=definite,possible,indirect --show-reachable=yes --num-callers=50",
    "valgrind2": "valgrind --leak-check=full --show-leak-kinds=definite,possible,indirect --expensive-definedness-checks=yes --show-reachable=yes --num-callers=50 --track-origins=yes",
    "valgrind_exit": True,
    "enable_tool_tips": True,
}

# Parameters of main window
prev_exe_file_list = []

# Parameters of wid_test_log
log_pane_height = 0
log_pane_solo_height = 0
trace_pane_height = 0
trace_pane_solo_height = 0

# Parameters of misc. dialogs
tc_list_geometry = ""
job_list_geometry = ""
help_win_geometry = ""


# internal state
tid_update_rc_sec = None
tid_update_rc_min = None

# "compat" := oldest version of gtest_gui that can parse this file
rcfile_compat = 0x01000000
rcfile_version = 0x01000003
rcfile_error = 0


def update_prev_exe_file_list(path):
    global prev_exe_file_list

    path = os.path.abspath(path)
    if not prev_exe_file_list or prev_exe_file_list[-1] != path:
        prev_exe_file_list = [x for x in prev_exe_file_list if x != path]
        prev_exe_file_list.append(path)

        rc_file_update_after_idle()


def get_rc_file_path():
    if (os.name == "posix"):
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        home = os.path.expanduser("~")

        if xdg_config_home is not None and os.path.exists(xdg_config_home):
            rc_file = os.path.join(xdg_config_home, "gtest_gui", "gtest_gui.rc")

        elif home is not None and os.path.exists(home):
            config_dir = os.path.join(home, ".config")
            if os.path.exists(config_dir) and os.path.isdir(config_dir):
                rc_file = os.path.join(home, ".config", "gtest_gui", "gtest_gui.rc")
            else:
                rc_file = os.path.join(home, ".gtest_gui.rc")

        else:
            rc_file = "gtest_gui.rc"

        os.makedirs(os.path.dirname(rc_file), exist_ok=True)

    else:
        # TODO
        rc_file = "gtest_gui.ini"

    return rc_file


def rc_file_load():
    global rcfile_version
    global log_pane_height, log_pane_solo_height
    global trace_pane_height, trace_pane_solo_height
    global tc_list_geometry, job_list_geometry, help_win_geometry
    global options
    global prev_exe_file_list

    font_content_opt = None
    font_trace_opt = None

    error = False
    ver_check = False
    rc_compat_version = None
    line_no = 0
    rc_path = get_rc_file_path()

    try:
        with open(rc_path, "r") as rcfile:
            for line in rcfile:
                line_no += 1
                if re.match(r"^\s*(?:#.*)?$", line):
                    continue

                match = re.match(r"^([a-z][a-z0-9_\:]*)=(.+)$", line)
                if match:
                    var = match.group(1)
                    try:
                        val = json.loads(match.group(2))

                        if   (var == "log_browser"):            options["browser"] = val
                        elif (var == "browser_stdin"):          options["browser_stdin"] = val
                        elif (var == "cmd_valgrind1"):          options["valgrind1"] = val
                        elif (var == "cmd_valgrind2"):          options["valgrind2"] = val
                        elif (var == "valgrind_exit"):          options["valgrind_exit"] = val
                        elif (var == "seed_regexp"):            options["seed_regexp"] = val
                        elif (var == "trace_dir"):              options["trace_dir"] = val
                        elif (var == "exit_clean_trace"):       options["exit_clean_trace"] = val
                        elif (var == "startup_import_trace"):   options["startup_import_trace"] = val
                        elif (var == "copy_executable"):        options["copy_executable"] = val
                        elif (var == "enable_tool_tips"):       options["enable_tool_tips"] = val

                        elif (var == "font_content"):           font_content_opt = val
                        elif (var == "font_trace"):             font_trace_opt = val
                        elif (var == "prev_exe_file_list"):     prev_exe_file_list = val

                        elif (var == "log_pane_height"):        log_pane_height = val
                        elif (var == "log_pane_solo_height"):   log_pane_solo_height = val
                        elif (var == "trace_pane_height"):      trace_pane_height = val
                        elif (var == "trace_pane_solo_height"): trace_pane_solo_height = val
                        elif (var == "tc_list_geometry"):       tc_list_geometry = val
                        elif (var == "job_list_geometry"):      job_list_geometry = val
                        elif (var == "help_win_geometry"):      help_win_geometry = val

                        elif (var == "rcfile_version"):         rcfile_version = val
                        elif (var == "rc_compat_version"):      rc_compat_version = val
                        elif (var == "rc_timestamp"):           pass
                        else:
                            print("Warning: ignoring unknown keyword in rcfile line %d:" % line_no, var, file=sys.stderr)

                    except json.decoder.JSONDecodeError:
                        tk_messagebox.showerror(parent=tk_utils.tk_top, message="Syntax error decoding rcfile line %d: %s" % (line_no, line[:40]))
                        error = True

                elif not error:
                    tk_messagebox.showerror(parent=tk_utils.tk_top, message="Syntax error in rc file, line #%d: %s" % (line_no, line[:40]))
                    error = True

                elif not ver_check:
                    # check if the given rc file is from a newer version
                    if rc_compat_version is not None:
                        if rc_compat_version > rcfile_version:
                            tk_messagebox.showerror(parent=tk_utils.tk_top,
                                                    message="rc file '%s' is from an incompatible, "
                                                    "newer version (%s) of this softare and cannot be loaded."
                                                    % (rc_path, rcfile_version))

                            # change name of rc file so that the newer one isn't overwritten
                            rc_path = rc_path + "." + rcfile_version
                            # abort loading further data (would overwrite valid defaults)
                            return

                        ver_check = True

        if font_content_opt:
            try:
                tk_utils.init_font_content(font_content_opt)
            except Exception as e:
                print("Error configuring content font:", str(e), file=sys.stderr)

        if font_trace_opt:
            try:
                tk_utils.init_font_trace(font_trace_opt)
            except Exception as e:
                print("Error configuring trace font:", str(e), file=sys.stderr)

    except OSError as e:
        if e.errno != errno.ENOENT:
            print("Failed to load config file " + rc_path + ":", str(e), file=sys.stderr)


def rc_file_update():
    global rcfile_error, rcfile_compat, rcfile_version
    global options, tid_update_rc_sec, tid_update_rc_min
    global log_pane_height, log_pane_solo_height
    global trace_pane_height, trace_pane_solo_height
    global tc_list_geometry, job_list_geometry, help_win_geometry
    global prev_exe_file_list

    if tid_update_rc_sec: tk_utils.tk_top.after_cancel(tid_update_rc_sec)
    if tid_update_rc_min: tk_utils.tk_top.after_cancel(tid_update_rc_min)
    tid_update_rc_sec = None
    tid_update_rc_min = None

    rc_path = get_rc_file_path()
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".tmp",
                                         dir=os.path.dirname(rc_path),
                                         prefix=os.path.basename(rc_path)) as rcfile:
            timestamp = str(datetime.now())
            print("#\n"
                  "# gtest_gui configuration file\n"
                  "#\n"
                  "# This file is automatically generated - do not edit\n"
                  "# Written at: %s\n"
                  "#\n" % timestamp, file=rcfile, end="")

            # dump software version
            print("rcfile_version=", json.dumps(rcfile_version), file=rcfile)
            print("rc_compat_version=", json.dumps(rcfile_compat), file=rcfile)
            print("rc_timestamp=", json.dumps(timestamp), file=rcfile)

            # dump configuration options
            print("log_browser=", json.dumps(options["browser"]), file=rcfile)
            print("browser_stdin=", json.dumps(options["browser_stdin"]), file=rcfile)
            print("cmd_valgrind1=", json.dumps(options["valgrind1"]), file=rcfile)
            print("cmd_valgrind2=", json.dumps(options["valgrind2"]), file=rcfile)
            print("valgrind_exit=", json.dumps(options["valgrind_exit"]), file=rcfile)
            print("seed_regexp=", json.dumps(options["seed_regexp"]), file=rcfile)
            print("trace_dir=", json.dumps(options["trace_dir"]), file=rcfile)
            print("exit_clean_trace=", json.dumps(options["exit_clean_trace"]), file=rcfile)
            print("startup_import_trace=", json.dumps(options["startup_import_trace"]), file=rcfile)
            print("copy_executable=", json.dumps(options["copy_executable"]), file=rcfile)
            print("enable_tool_tips=", json.dumps(options["enable_tool_tips"]), file=rcfile)

            # dump font selection
            print("font_content=", json.dumps(tk_utils.font_content.configure()), file=rcfile)
            print("font_trace=", json.dumps(tk_utils.font_trace.configure()), file=rcfile)

            # dump executable file history
            print("prev_exe_file_list=", json.dumps(prev_exe_file_list), file=rcfile)

            # dump dialog geometry hints
            print("log_pane_height=", json.dumps(log_pane_height), file=rcfile)
            print("log_pane_solo_height=", json.dumps(log_pane_solo_height), file=rcfile)
            print("trace_pane_height=", json.dumps(trace_pane_height), file=rcfile)
            print("trace_pane_solo_height=", json.dumps(trace_pane_solo_height), file=rcfile)
            print("tc_list_geometry=", json.dumps(tc_list_geometry), file=rcfile)
            print("job_list_geometry=", json.dumps(job_list_geometry), file=rcfile)
            print("help_win_geometry=", json.dumps(help_win_geometry), file=rcfile)

        # copy attributes on the new file
        try:
            st = os.stat(rc_path)
            try:
                os.chmod(rcfile.name, st.st_mode & 0o777)
                if (os.name == "posix"):
                    os.chown(rcfile.name, st.st_uid, st.st_gid)
            except OSError as e:
                print("Warning: Failed to update mode/permissions on %s: %s" % (rc_path, e.strerror), file=sys.stderr)
        except OSError as e:
            pass

        # move the new file over the old one
        try:
            # MS-Windows does not allow renaming when the target file already exists,
            # therefore remove the target first. Disadvantage: operation is not atomic.
            if (os.name != "posix"):
                try:
                    os.remove(rc_path)
                except OSError:
                    pass
            os.rename(rcfile.name, rc_path)
            rcfile_error = False
        except OSError as e:
            if not rcfile_error:
                tk_messagebox.showerror(parent=tk_utils.tk_top, message="Could not replace rc file %s with temporary %s: %s" % (rc_path, rcfile.name, e.strerror))
            rcfile_error = True
            os.remove(rcfile.name)

    except OSError as e:
        # write error - remove the file fragment, report to user
        if not rcfile_error:
            rcfile_error = True
            tk_messagebox.showerror(parent=tk_utils.tk_top, message="Failed to write file %s: %s" % (rcfilename, e.strerror))
        os.remove(rcfile.name)

    return not rcfile_error

#
# This function is used to trigger writing the RC file after changes.
# The write is delayed by a few seconds to avoid writing the file multiple
# times when multiple values are changed. This timer is restarted when
# another change occurs during the delay, however only up to a limit.
#
def rc_file_update_after_idle():
    global tid_update_rc_sec, tid_update_rc_min

    if tid_update_rc_sec: tk_utils.tk_top.after_cancel(tid_update_rc_sec)
    tid_update_rc_sec = tk_utils.tk_top.after(3000, rc_file_update)

    if not tid_update_rc_min:
        tid_update_rc_min = tk_utils.tk_top.after(60000, rc_file_update)


def rc_file_update_upon_exit():
    if tid_update_rc_sec or tid_update_rc_min:
        rc_file_update()

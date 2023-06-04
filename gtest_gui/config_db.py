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
Database and persistent storage for configuration parameters. Parameters are
read from a file into memory once during start-up. Various modules access the
database when needed using getters. Updates are done via setters and
automatically trigger an update of the configuration file after a short delay
timer (for combining multiple consecutive changes), or at latest upon shutdown.
The module does not provide notifications about configuration parameter changes.
"""

import errno
from datetime import datetime
import json
import os
import re
import sys
import tempfile
import tkinter as tk
from tkinter import messagebox as tk_messagebox

import gtest_gui.tk_utils as tk_utils

# Module "appdirs" is required on Windows to learn the directory where to store
# application configuration files. Install the module via "pip3 install appdirs"
# if the import fails. (Alternatively, you could replace the one function call
# into the module with a hard-coded path.)
if sys.platform == "win32":
    import appdirs

#
# Database of configuration options and other persistent state to be written to
# the configuration file. Default values assigned here are overridden when
# loading the configuration file. Therefore they are only used when a user starts
# the application for the first time after installation.
#
options = {
    # Options set via configuration menu
    "log_browser": "trowser.py",
    "browser_stdin": True,
    "seed_regexp": "",
    "trace_dir": "",
    "exit_clean_trace": True,
    "startup_import_trace": True,
    "copy_executable": True,
    "cmd_valgrind1": "valgrind --leak-check=full "
                     "--show-leak-kinds=definite,possible,indirect "
                     "--show-reachable=yes --num-callers=50",
    "cmd_valgrind2": "valgrind --leak-check=full "
                     "--show-leak-kinds=definite,possible,indirect "
                     "--show-reachable=yes --num-callers=50 "
                     "--track-origins=yes --expensive-definedness-checks=yes",
    "valgrind_exit": True,
    "enable_tool_tips": True,

    # Parameters of class TextLogWidget
    "log_pane_height": 0,
    "log_pane_solo_height": 0,
    "trace_pane_height": 0,
    "trace_pane_solo_height": 0,

    # Parameters of misc. dialog classes
    "tc_list_geometry": "",
    "job_list_geometry": "",
    "help_win_geometry": "",

    # Parameters of class MainWindow
    "prev_exe_file_list": [],
}

# internal state
tid_update_rc_sec = None
tid_update_rc_min = None

# "compat" := oldest version of gtest_gui that can parse this file
RCFILE_COMPAT = 0x01000000
RCFILE_VERSION = 0x01000003
rcfile_name_appendix = ""
rcfile_error = False


def get_opt(name):
    """ Return the configured value for the named option. """
    return options[name]


def set_opt(name, value):
    """
    Update the configuration value for the named option in memory and RC file.
    File update is delayed a few seconds for bundling updates after consecutive
    configuration changes.
    """
    if options[name] != value:
        options[name] = value
        __rc_file_update_after_idle()


def update_prev_exe_file_list(path):
    """
    Add the given path to the list of previously used executable files, or move
    it to the front of the list if already in it. Afterwards update the
    RC file to store the new list value.
    """
    path = os.path.abspath(path)
    prev_list = options["prev_exe_file_list"]
    if not prev_list or prev_list[-1] != path:
        prev_list = [x for x in prev_list if x != path]
        prev_list.append(path)
        options["prev_exe_file_list"] = prev_list

        __rc_file_update_after_idle()


def update_fonts():
    """
    Trigger update of the RC file after a font configuration change. The font
    options are retrieved dynamically during the update.
    """
    __rc_file_update_after_idle()


def __load_rc_value(var, val, font_opts):
    result = True

    if var in options:
        options[var] = val

    elif var == "font_content":
        font_opts[0] = val
    elif var == "font_trace":
        font_opts[1] = val

    else:
        result = False

    return result


def __write_rc_values(rcfile):
    # dump configuration options
    for var in options:
        print(var + "=" + json.dumps(options[var]), file=rcfile)

    # dump font selection
    print("font_content=", json.dumps(tk_utils.font_content.configure()), file=rcfile)
    print("font_trace=", json.dumps(tk_utils.font_trace.configure()), file=rcfile)


def __get_rc_file_path():
    if os.name == "posix":
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

        rc_file += rcfile_name_appendix

        os.makedirs(os.path.dirname(rc_file), exist_ok=True)

    else:
        # Query system library for the common path for application configuration.
        # e.g. on Win10: C:\Users\USERNAME\AppData\Local\GtestGui (hidden directory)
        config_dir = appdirs.user_config_dir(appname="GtestGui", appauthor=False)
        os.makedirs(config_dir, exist_ok=True)

        rc_file = os.path.join(config_dir, "gtest_gui.rc")

    return rc_file


def rc_file_load():
    """ Parse the configuration file and load option values into memory. """
    font_opts = [None, None]
    error = False
    line_no = 0
    rc_path = __get_rc_file_path()
    file_version = 0

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

                        if var == "rc_compat_version":
                            # check if the given rc file is from a newer version
                            if val > RCFILE_VERSION:
                                msg = "RC file '%s' is from an incompatible, " \
                                      "newer version (%s) of this software (version %s) " \
                                      "and cannot be loaded." \
                                      % (rc_path, file_version if file_version > val else val,
                                         RCFILE_VERSION)
                                tk_messagebox.showerror(parent=tk_utils.tk_top, message=msg)

                                # change name of rc file so that the newer one isn't overwritten
                                global rcfile_name_appendix
                                rcfile_name_appendix = "." + val
                                # abort loading further data (would overwrite valid defaults)
                                return
                        elif var == "rcfile_version":
                            file_version = val
                        elif var == "rc_timestamp":
                            pass
                        elif not __load_rc_value(var, val, font_opts):
                            print("Warning: ignoring unknown keyword in rcfile line %d:"
                                  % line_no, var, file=sys.stderr)

                    except json.decoder.JSONDecodeError:
                        tk_messagebox.showerror(parent=tk_utils.tk_top,
                                                message="Syntax error decoding rcfile line %d: %s"
                                                % (line_no, line[:40]))
                        error = True

                elif not error:
                    tk_messagebox.showerror(parent=tk_utils.tk_top,
                                            message="Syntax error in rc file, line #%d: %s"
                                            % (line_no, line[:40]))
                    error = True

        if font_opts[0]:
            try:
                tk_utils.init_font_content(font_opts[0])
            except tk.TclError as exc:
                print("Error configuring content font:", str(exc), file=sys.stderr)

        if font_opts[1]:
            try:
                tk_utils.init_font_trace(font_opts[1])
            except tk.TclError as exc:
                print("Error configuring trace font:", str(exc), file=sys.stderr)

    except OSError as exc:
        if exc.errno != errno.ENOENT:
            print("Failed to load config file " + rc_path + ":", str(exc), file=sys.stderr)


def __rc_file_update():
    global rcfile_error
    global tid_update_rc_sec, tid_update_rc_min

    if tid_update_rc_sec:
        tk_utils.tk_top.after_cancel(tid_update_rc_sec)
        tid_update_rc_sec = None
    if tid_update_rc_min:
        tk_utils.tk_top.after_cancel(tid_update_rc_min)
        tid_update_rc_min = None

    rc_path = __get_rc_file_path()
    tmp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".tmp",
                                         dir=os.path.dirname(rc_path),
                                         prefix=os.path.basename(rc_path)) as rcfile:
            tmp_file_path = rcfile.name
            timestamp = str(datetime.now())
            print("#\n"
                  "# gtest_gui configuration file\n"
                  "#\n"
                  "# This file is automatically generated - do not edit\n"
                  "# Written at: %s\n"
                  "#\n" % timestamp, file=rcfile, end="")

            # dump software version
            print("rcfile_version=", json.dumps(RCFILE_VERSION), file=rcfile)
            print("rc_compat_version=", json.dumps(RCFILE_COMPAT), file=rcfile)
            print("rc_timestamp=", json.dumps(timestamp), file=rcfile)

            # write option values
            __write_rc_values(rcfile)

        # copy attributes on the new file
        try:
            stt = os.stat(rc_path)
            try:
                os.chmod(tmp_file_path, stt.st_mode & 0o777)
                if os.name == "posix":
                    os.chown(tmp_file_path, stt.st_uid, stt.st_gid)
            except OSError as exc:
                if not rcfile_error:
                    rcfile_error = True
                    msg = ("Warning: Failed to update file mode/permissions on "
                           "configuration file %s: %s") % (rc_path, exc.strerror)
                    tk_messagebox.showerror(parent=tk_utils.tk_top, message=msg)
        except OSError:
            pass

        # move the new file over the old one
        try:
            # MS-Windows does not allow renaming when the target file already exists,
            # therefore remove the target first. Disadvantage: operation is not atomic.
            if os.name != "posix":
                try:
                    os.remove(rc_path)
                except OSError:
                    pass
            os.rename(tmp_file_path, rc_path)
            rcfile_error = False
        except OSError as exc:
            if not rcfile_error:
                rcfile_error = True
                msg = "Could not replace configuration file %s with temporary %s: %s" % \
                      (rc_path, tmp_file_path, exc.strerror)
                tk_messagebox.showerror(parent=tk_utils.tk_top, message=msg)
            os.remove(tmp_file_path)

    except OSError as exc:
        if tmp_file_path:
            # write error - remove the file fragment, report to user
            if not rcfile_error:
                rcfile_error = True
                msg = "Failed to write temporary file %s for configuration file update: %s" % \
                      (rc_path, exc.strerror)
                tk_messagebox.showerror(parent=tk_utils.tk_top, message=msg)
            os.remove(tmp_file_path)
        else:
            # failed to create temporary file
            if not rcfile_error:
                rcfile_error = True
                msg = "Failed to create temporary file in directory of %s: %s" % \
                      (rc_path, exc.strerror)
                tk_messagebox.showerror(parent=tk_utils.tk_top, message=msg)

    return not rcfile_error

#
# This function is used to trigger writing the RC file after changes.
# The write is delayed by a few seconds to avoid writing the file multiple
# times when multiple values are changed. This timer is restarted when
# another change occurs during the delay, however only up to a limit.
#
def __rc_file_update_after_idle():
    global tid_update_rc_sec, tid_update_rc_min

    if tid_update_rc_sec:
        tk_utils.tk_top.after_cancel(tid_update_rc_sec)
    tid_update_rc_sec = tk_utils.tk_top.after(3000, __rc_file_update)

    if not tid_update_rc_min:
        tid_update_rc_min = tk_utils.tk_top.after(60000, __rc_file_update)


def rc_file_update_synchronously():
    """ Update the RC file immediately in case an update is pending. """
    global rcfile_error
    if tid_update_rc_sec or tid_update_rc_min or rcfile_error:
        # warn again if previous update failed
        rcfile_error = False

        return __rc_file_update()

    return True

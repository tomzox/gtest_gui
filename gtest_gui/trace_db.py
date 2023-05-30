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
This modules defines functions for managing trace output and core dump files.
The files are organized in a tree whose root is located at a configured
absolute path, or the current directory, if none is configured. There's a
subdirectory for each different executable timestamp that generated trace
output.
"""

import os
import re
import sys

from tkinter import messagebox as tk_messagebox

import gtest_gui.config_db as config_db
import gtest_gui.test_db as test_db
import gtest_gui.tk_utils as tk_utils



def first_free_trace_file_idx(exe_ts):
    """
    Returns an index parameter value for get_trace_file_name().
    This function may throw OSError.
    """
    free_idx = 0
    for entry in os.scandir(get_trace_dir(exe_ts)):
        if entry.is_file():
            match = re.match(r"^trace\.(\d+)$", entry.name)
            if match:
                this_idx = int(match.group(1))
                if this_idx >= free_idx:
                    free_idx = this_idx + 1
    return free_idx


def get_trace_file_name(exe_ts, idx):
    """
    Returns a file name for a trace output file that does not yet exist. The
    index has to be determined initiall via first_free_trace_file_idx() and
    incremented after each call.
    """
    return os.path.join(get_trace_dir(exe_ts), "trace.%d" % idx)


def search_trace_sub_dirs():
    """
    Returns a list of all trace files found in the configured trace directory
    tree. This function may throw OSError.
    """
    if config_db.get_opt("trace_dir"):
        trace_dir_path = config_db.get_opt("trace_dir")
    else:
        trace_dir_path = "."

    trace_files = []
    for base_entry in os.scandir(trace_dir_path):
        if base_entry.is_dir() and re.match(r"^trace\.\d+$", base_entry.name):
            for entry in os.scandir(os.path.join(trace_dir_path, base_entry.name)):
                if entry.is_file() and re.match(r"^trace\.(\d+)$", entry.name):
                    trace_files.append(os.path.join(trace_dir_path,
                                                    base_entry.name, entry.name))

    return trace_files


def get_trace_dir(exe_ts):
    """ Returns the path of the trace sub-directory for the given executable file. """
    trace_dir_path = "trace.%d" % exe_ts
    if config_db.get_opt("trace_dir"):
        trace_dir_path = os.path.join(config_db.get_opt("trace_dir"), trace_dir_path)
    return trace_dir_path


def get_exe_file_link_name(exe_name, exe_ts):
    """
    Returns the full path of the executable to use when spawning test
    processes. This may be the executable file itself, or a copy within the
    trace output directory, if this option is configured.
    """
    if config_db.get_opt("copy_executable"):
        trace_dir_path = get_trace_dir(exe_ts)
        return os.path.join(trace_dir_path, os.path.basename(exe_name))

    return exe_name


def _get_temp_name_for_trace(file_name, file_off, is_extern_import):
    # For a file given on the command line use the full path (with "/"
    # replaced) plus a unique prefix in case it's not an absolute path.
    if is_extern_import:
        return "imported!" + file_name.replace(os.path.sep, "!") + "." + str(file_off)

    # For traces within the regular tree, only use the sub-dir and file name
    # with file offset as suffix.
    trace_path, trace_name = os.path.split(file_name)
    return "%s.%s.%d" % (os.path.basename(trace_path), trace_name, file_off)


def get_core_file_name(trace_name, is_valgrind):
    """
    Returns the name of a core file corresponding to the given trace file.
    """
    split_name = os.path.split(trace_name)
    core_name = "vgcore" if is_valgrind else "core"

    return os.path.join(split_name[0], core_name + "." + split_name[1])


def release_exe_file_copy(exe_name=None, exe_ts=None):
    """
    Automatically delete the copy of an executable file in a trace directory,
    when all dependencies have been removed. Dependencies are the executable
    version still being test target (i.e. timestamp on original executable file
    unchanged), or core files generated by the same executable version. This
    function has to be called after executable file updates or trace/core file
    removal.
    """
    if exe_name is None:
        exe_name = test_db.test_exe_name
    if exe_ts is None:
        exe_ts = test_db.test_exe_ts
    if not exe_name or not exe_ts:
        return

    if not config_db.get_opt("copy_executable"):
        return

    trace_dir_path = get_trace_dir(exe_ts)
    if os.path.exists(trace_dir_path):
        dir_list = os.listdir(trace_dir_path)

        if not any(x.startswith(("core.", "vgcore.")) for x in dir_list):
            exe_link = get_exe_file_link_name(exe_name, exe_ts)
            try:
                os.unlink(exe_link)
                try:
                    dir_list.remove(os.path.basename(exe_link))
                except ValueError:
                    pass
            except OSError:
                pass

            if not dir_list:
                try:
                    os.rmdir(trace_dir_path)
                except OSError:
                    pass


def remove_trace_or_core_files(rm_files, rm_exe):
    """
    Removes the given trace output files and copies of the executables.
    """
    if config_db.get_opt("copy_executable"):
        for exe_name_ts in rm_exe:
            rm_files.add(get_exe_file_link_name(exe_name_ts[0], exe_name_ts[1]))

    try:
        for file_name in rm_files:
            os.remove(file_name)
    except OSError:
        pass

    rm_dirs = {os.path.dirname(x) for x in rm_files}
    for adir in rm_dirs:
        try:
            if not os.listdir(adir):
                os.rmdir(adir)
        except OSError:
            pass


def clean_all_trace_files(clean_failed=False):
    """
    Automatically cleans either all trace output files, ot trace output from
    all passed test cases. For trace files containing output from both failed
    and passed tests, the files are rewritten to remove output from passed test
    cases.
    """
    contains_fail = set()
    pass_parts = {}
    rm_files = set()
    rm_exe = set()
    for log in test_db.test_results:
        # never auto-clean imported files: could interfere with other GUI instance
        if log[4] and not log[13]:
            rm_files.add(log[4])
            if not clean_failed:
                if log[3] == 2 or log[3] == 3:
                    contains_fail.add(log[4])
                elif log[3] == 4: # valgrind: keep all pass traces
                    del pass_parts[log[4]]
                else:
                    _add_passed_section(pass_parts, log[4], log[5], log[6])

        if clean_failed and log[7]:
            rm_files.add(log[7])
            if log[1]:
                rm_exe.add((log[1], log[2]))

    if not clean_failed:
        for name in contains_fail:
            rm_files.remove(name)
            parts = pass_parts.get(name)
            if parts:
                _compress_trace_file(name, parts)

    remove_trace_or_core_files(rm_files, rm_exe)


def _add_passed_section(pass_parts, name, start, length):
    parts = pass_parts.get(name)
    if parts:
        if parts[-1][1] == start:
            parts[-1][1] = start + length
        else:
            pass_parts[name].append([start, start + length])
    else:
        pass_parts[name] = [[start, start + length]]


def _compress_trace_file(name, parts):
    try:
        with open(name, "r+b") as file_obj:
            size = os.stat(name).st_size
            off = parts[0][0]
            # pylint: disable=consider-using-enumerate
            for idx in range(len(parts)):
                next_start = parts[idx + 1][0] if (idx + 1 < len(parts)) else size
                cur_end = parts[idx][1]

                file_obj.seek(cur_end)
                data = file_obj.read(next_start - cur_end)

                file_obj.seek(off)
                file_obj.write(data)

                off += len(data)
                idx += 1

            file_obj.truncate(off)

    except OSError:
        pass


def extract_trace(file_name, file_offs, length):
    """
    Reads the given portion of the given trace output file and returns it as a string.
    """
    try:
        with open(file_name, "rb") as file_obj:
            if file_obj.seek(file_offs) == file_offs:
                snippet = file_obj.read(length)
                if snippet:
                    return snippet.decode(errors="backslashreplace")
    except OSError as exc:
        # use print as this function may be called from context of secondary threads
        print("Failed to read trace file:" + str(exc), file=sys.stderr)

    return None


def extract_trace_to_temp_file(tmp_dir, trace_name, file_offs, length, is_extern_import):
    """
    Creates a temporary file that contains a copy of only the given portion of
    the trace file. The caller is responsible for removing the file after it is
    no longer used.
    """
    tmp_name = os.path.join(tmp_dir,
                            _get_temp_name_for_trace(trace_name, file_offs, is_extern_import))
    if not os.path.exists(tmp_name):
        try:
            with open(trace_name, "rb") as fread:
                if fread.seek(file_offs) == file_offs:
                    with open(tmp_name, "wb") as fwrite:
                        snippet = fread.read(length)
                        fwrite.write(snippet)
        except OSError as exc:
            tk_messagebox.showerror(parent=tk_utils.tk_top,
                                    message="Failed to copy trace to temporary file: " + str(exc))
            tmp_name = None

    return tmp_name

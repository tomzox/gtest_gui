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
import re
import subprocess
import sys
import tempfile
import threading

if (os.name == "posix"): import fcntl

import tkinter as tk
from tkinter import messagebox as tk_messagebox
from tkinter import filedialog as tk_filedialog

import gtest_gui.config_db as config_db
import gtest_gui.gtest as gtest
import gtest_gui.test_db as test_db
import gtest_gui.tk_utils as tk_utils
import gtest_gui.wid_status_line as wid_status_line

prev_trace_export_path = ""

temp_dir = None

def __get_temp_dir_name():
    global temp_dir
    if not temp_dir:
        temp_dir = tempfile.TemporaryDirectory(prefix="gtest_gui_tmp")
    return temp_dir.name


def show_trace_snippet(tk_top, file_name, file_off, length, is_extern_import):
    browser_cmd = config_db.options["browser"]
    if not browser_cmd:
        wid_status_line.show_message("error", "No trace browser app is configured")
        return

    if config_db.options["browser_stdin"]:
        txt = gtest.extract_trace(file_name, file_off, length)
        if txt is None:
            wid_status_line.show_message("error", "Failed to read trace file")
            return
        elif txt == "":
            wid_status_line.show_message("error", "Trace empty for this result")
            return
        file_name = "-"
        shared_file = None

    else:
        file_name = gtest.extract_trace_to_temp_file(__get_temp_dir_name(),
                                                     file_name, file_off, length, is_extern_import)
        if not file_name:
            return
        shared_file = file_name
        txt = ""

    Proc_monitor.create(re.split(r"\s+", browser_cmd) + [file_name], txt, shared_file)


def show_trace(tk_top, file_name):
    browser_cmd = config_db.options["browser"]
    if browser_cmd:
        Proc_monitor.create(re.split(r"\s+", browser_cmd) + [file_name], "", None)
    else:
        wid_status_line.show_message("error", "No trace browser app is configured")


def show_stack_trace(tk_top, tc_name, exe_name, exe_ts, core_name):
    cmd_filename = os.path.join(__get_temp_dir_name(), "gdb_command.bat")
    if not os.path.exists(cmd_filename):
        try:
            with open(cmd_filename, "w") as f:
                print("info thread", file=f)
                print("thread apply all backtrace", file=f)
        except Exception as e:
            msg = "Error writing command input file for gdb: " + str(e)
            tk_messagebox.showerror(parent=tk_top, message=msg)
            return

    if not exe_name:
        msg = "Executable from which this core originates is unknown. " \
              "Use current executable? Press 'No' to manually select an executable."
        answer = tk_messagebox.askyesnocancel(parent=tk_top, message=msg)
        if answer is None:
            return
        if not answer:
            if (os.name == "posix"):
                filetypes = [("all", "*"), ("Executable", "*.exe")]
            else:
                filetypes = [("Executable", "*.exe"), ("all", "*")]
            exe_file = tk_filedialog.askopenfilename(
                            parent=tk_top, filetypes=filetypes,
                            title="Select test executable",
                            initialfile="",
                            initialdir=os.path.dirname(core_name))
            if not exe_file:
                return
        else:
            exe_file = test_db.test_exe_name
    else:
        exe_file = gtest.gtest_control_get_exe_file_link_name(exe_name, exe_ts)

    try:
        cmd = ["gdb", "-batch", "-x", cmd_filename, exe_file, core_name]
        # Null device to prevent gdb from getting suspended by SIGTTIN
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, text=True)
        flags = fcntl.fcntl(proc.stdout, fcntl.F_GETFL)
        fcntl.fcntl(proc.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    except Exception as e:
        tk_messagebox.showerror(parent=tk_top, message="Failed to run gdb: " + str(e))
        return

    title = "GtestGui: Stack trace - %s (%s)" % (tc_name, core_name)
    Log_browser(tk_top, title, proc)


def export_traces(tk_top, log_idx_sel):
    global prev_trace_export_path

    types = [("ZIP archive", "*.zip"), ("all", "*")]
    out_name = tk_filedialog.asksaveasfilename(
                    parent=tk_top, filetypes=types,
                    title="Select output file for trace export",
                    initialfile=os.path.basename(prev_trace_export_path),
                    initialdir=os.path.dirname(prev_trace_export_path))
    if not out_name:
        return

    out_name = os.path.abspath(out_name)
    prev_trace_export_path = out_name

    with tempfile.TemporaryDirectory() as tempdir:
        file_list = []
        file_idx = 0
        for log_idx in log_idx_sel:
            log = test_db.test_results[log_idx]
            if log[4]:
                txt = gtest.extract_trace(log[4], log[5], log[6])
                if txt:
                    filename = "trace.%d.%s" % (file_idx, log[0])
                    abs_filename = os.path.join(tempdir, filename)
                    try:
                        with open(abs_filename, "w") as f:
                            f.write(txt)
                    except OSError as e:
                        tk_messagebox.showerror(
                            parent=tk_top,
                            message="Failed to write temporary file: " + str(e))
                        break

                    file_list.append(filename)
                    file_idx += 1

        if file_list:
            try:
                cmd = ["zip", "-9", out_name]
                cmd.extend(file_list)
                proc = subprocess.run(cmd, check=True, timeout=20, cwd=tempdir,
                                      stdout=subprocess.DEVNULL)
            except Exception as e:
                tk_messagebox.showerror(parent=tk_top,
                                        message="Failed to create archive: " + str(e))



# ----------------------------------------------------------------------------
#
# Mini dialog only used for displaying text snippets
#
class Log_browser(object):
    def __init__(self, tk_top, title, proc):
        wid_top = tk.Toplevel(tk_top)
        wid_top.wm_group(tk_top)
        wid_top.wm_title(title)

        wid_txt = tk.Text(wid_top, width=100, height=50, wrap=tk.NONE, relief=tk.FLAT,
                          font=tk_utils.font_content, insertofftime=0, cursor="top_left_arrow")
        wid_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=1, padx=5, pady=5)

        wid_sb = tk.Scrollbar(wid_top, orient=tk.VERTICAL, command=wid_txt.yview, takefocus=0)
        wid_sb.pack(side=tk.LEFT, fill=tk.Y)
        wid_txt.configure(yscrollcommand=wid_sb.set)

        wid_txt.bindtags([wid_txt, "TextReadOnly", wid_top, "all"])
        wid_txt.bind("<Alt-Key-w>", lambda e: self.__do_toggle_line_wrap())
        wid_txt.bind("<Destroy>", lambda e: self.__destroy_window())

        wid_txt.focus_set()
        self.wid_txt = wid_txt

        if isinstance(proc, str):
            wid_txt.insert("1.0", proc)
            self.proc = None
            self.timer_id = None
        else:
            wid_txt.insert("1.0", "\nApplication running, please stand by...\n")

            self.proc = proc
            self.timer_id = tk_utils.tk_top.after(500, self.__handle_communicate)
            self.is_empty = True


    def __handle_communicate(self):
        txt = self.proc.stdout.read(32*1024)
        if txt:
            if self.is_empty:
                self.is_empty = False
                self.wid_txt.delete("1.0", "end")

            self.wid_txt.insert("end", txt)
            self.timer_id = tk_utils.tk_top.after(100, self.__handle_communicate)

        elif self.proc.poll() is None:
            self.timer_id = tk_utils.tk_top.after(250, self.__handle_communicate)

        else:
            # leave the process as zombie - Python will clean up eventually
            self.timer_id = None
            self.proc = None


    def __do_toggle_line_wrap(self):
        cur = self.wid_txt.cget("wrap")
        if cur == "none":
            self.wid_txt.configure(wrap=tk.CHAR)
        else:
            self.wid_txt.configure(wrap=tk.NONE)


    def __destroy_window(self):
        if self.timer_id:
            tk_utils.tk_top.after_cancel(self.timer_id)
            self.timer_id = None
        if self.proc:
            self.proc.terminate()
            self.proc = None


# ----------------------------------------------------------------------------
#
# Helper class for monitoring external application
# - catching error messages
# - cleaning up temporary input file after exit

class Proc_monitor(object):
    procs = []
    shared_files = {}
    tid = None

    @staticmethod
    def create(cmd, txt, file_name):
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if file_name:
                Proc_monitor.alloc_shared_file(file_name)

            Proc_monitor.procs.append(Proc_monitor(proc, txt, file_name))

            if Proc_monitor.tid is None:
                Proc_monitor.tid = tk_utils.tk_top.after(1000, Proc_monitor.proc_monitor)

        except Exception as e:
            tk_messagebox.showerror(parent=tk_utils.tk_top,
                                    message="Failed to start external trace browser: " + str(e))


    @staticmethod
    def alloc_shared_file(name):
        if Proc_monitor.shared_files.get(name, None):
            Proc_monitor.shared_files[name] += 1
        else:
            Proc_monitor.shared_files[name] = 1


    @staticmethod
    def release_shared_file(name):
        reg = Proc_monitor.shared_files.get(name, None)
        if reg is not None:
            if reg > 1:
                Proc_monitor.shared_files[name] -= 1
            else:
                del Proc_monitor.shared_files[name]
                try:
                    os.unlink(name)
                except OSError:
                    pass


    @staticmethod
    def remove(proc):
        Proc_monitor.procs = [x for x in Proc_monitor.procs if x is not proc]
        if not Proc_monitor.procs and Proc_monitor.tid:
            tk_utils.tk_top.after_cancel(Proc_monitor.tid)
            Proc_monitor.tid = None


    @staticmethod
    def proc_monitor():
        for proc in Proc_monitor.procs:
            proc.monitor()

        if Proc_monitor.procs:
            Proc_monitor.tid = tk_utils.tk_top.after(1000, Proc_monitor.proc_monitor)
        else:
            Proc_monitor.tid = None


    def __init__(self, proc, txt, file_name):
        self.file_name = file_name
        self.done = False
        self.stderr = None
        self.proc = proc
        self.thr = threading.Thread(target=lambda:self.__thread_browser(txt), daemon=True)
        self.thr.start()


    def __thread_browser(self, txt):
        output = self.proc.communicate(input=txt)

        self.stderr = output[1]
        self.done = True


    def monitor(self):
        if self.done:
            if self.proc.returncode != 0:
                msg = "External trace browser reported error code %d: %s" % \
                        (self.proc.returncode, self.stderr)
                tk_messagebox.showerror(parent=tk_utils.tk_top, message=msg)
            if self.file_name:
                Proc_monitor.release_shared_file(self.file_name)
            Proc_monitor.remove(self)



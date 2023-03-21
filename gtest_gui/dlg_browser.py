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
import subprocess
import sys
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

def show_trace_snippet(tk_top, file_name, file_off, length):
    txt = gtest.extract_trace(file_name, file_off, length)
    if txt:
        browser_exe = config_db.options["browser"]

        # TODO delete temporary
        if not config_db.options["browser_stdin"]:
            tmp_name = file_name + "." + str(file_off)
            with open(tmp_name, "w") as f:
                f.write(txt)
            cmd = browser_exe + " " + tmp_name
        else:
            cmd = browser_exe + " -"

        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True, shell=True)
            threading.Thread(target=lambda:thread_browser(proc, txt), daemon=True).start()
        except Exception as e:
            tk_messagebox.showerror(parent=tk_top, message="Failed to start external trace browser: " + str(e))
    elif txt is None:
        wid_status_line.show_message("error", "Failed to read trace file")
    else:
        wid_status_line.show_message("error", "Trace empty for this result")


def show_trace(tk_top, file_name):
    browser_exe = config_db.options["browser"]
    try:
        proc = subprocess.Popen([browser_exe, file_name])
        threading.Thread(target=lambda:thread_browser(proc, None),
                         daemon=True).start()
    except Exception as e:
        tk_messagebox.showerror(parent=tk_top,
                                message="Failed to start external trace browser: " + str(e))


def thread_browser(proc, txt):
    if txt:
        proc.communicate(input=txt)
    else:
        proc.wait()

    if proc.returncode != 0:
        # Report errors to STDERR as Tk is inaccessible from other threads
        print("External trace browser exited with code %d" % proc.returncode, file=sys.stderr)


def show_stack_trace(tk_top, tc_name, core_name):
    cmd_filename = ".gdb_command.bat"
    try:
        with open(cmd_filename, "w") as f:
            print("info thread", file=f)
            print("thread apply all backtrace", file=f)
    except Exception as e:
        msg = "Error writing command input file for gdb: " + str(e)
        tk_messagebox.showerror(parent=tk_top, message=msg)
        return

    try:
        cmd = ["gdb", "-batch", "-x", cmd_filename, test_db.test_exe_name, core_name]
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

    # TODO
    #try:
    #    os.remove(cmd_filename)
    #except OSError:
    #    pass


def export_traces(tk_top, log_idx_sel):
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
                    except:
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

        wid_txt = tk.Text(wid_top, width=100, height=60, wrap=tk.NONE, relief=tk.FLAT,
                          font=tk_utils.font_content, insertofftime=0, cursor="top_left_arrow")
        wid_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=1, padx=5, pady=5)

        wid_sb = tk.Scrollbar(wid_top, orient=tk.VERTICAL, command=wid_txt.yview, takefocus=0)
        wid_sb.pack(side=tk.LEFT, fill=tk.Y)
        wid_txt.configure(yscrollcommand=wid_sb.set)

        wid_txt.bindtags([wid_txt, "TextReadOnly", wid_top, "all"])
        wid_txt.bind("<Alt-Key-w>", lambda e: self.do_toggle_line_wrap())
        wid_txt.bind("<Destroy>", lambda e: self.destroy_window())

        wid_txt.focus_set()
        self.wid_txt = wid_txt

        if isinstance(proc, str):
            wid_txt.insert("1.0", proc)
            self.proc = None
            self.timer_id = None
        else:
            wid_txt.insert("1.0", "\nApplication running, please stand by...\n")

            self.proc = proc
            self.timer_id = tk_utils.tk_top.after(500, self.handle_communicate)
            self.is_empty = True


    def handle_communicate(self):
        txt = self.proc.stdout.read(32*1024)
        if txt:
            if self.is_empty:
                self.is_empty = False
                self.wid_txt.delete("1.0", "end")

            self.wid_txt.insert("end", txt)
            self.timer_id = tk_utils.tk_top.after(100, self.handle_communicate)

        elif self.proc.poll() is None:
            self.timer_id = tk_utils.tk_top.after(250, self.handle_communicate)

        else:
            # leave the process as zombie - Python will clean up eventually
            self.timer_id = None
            self.proc = None


    def do_toggle_line_wrap(self):
        cur = self.wid_txt.cget("wrap")
        if cur == "none":
            self.wid_txt.configure(wrap=tk.CHAR)
        else:
            self.wid_txt.configure(wrap=tk.NONE)


    def destroy_window(self):
        if self.timer_id:
            tk_utils.tk_top.after_cancel(self.timer_id)
            self.timer_id = None
        if self.proc:
            self.proc.terminate()
            self.proc = None

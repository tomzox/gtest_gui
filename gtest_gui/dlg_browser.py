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
Implements function interfaces for using external applications for displaying
trace file content, stack traces and for exporting trace files.
"""

import os
import re
import subprocess
import tempfile
import threading

import tkinter as tk
from tkinter import messagebox as tk_messagebox
from tkinter import filedialog as tk_filedialog

import gtest_gui.config_db as config_db
import gtest_gui.test_db as test_db
import gtest_gui.trace_db as trace_db
import gtest_gui.tk_utils as tk_utils
from gtest_gui.wid_status_line import StatusLineWidget

if os.name == "posix":
    import fcntl

prev_trace_export_path = ""

temp_dir = None

def __get_temp_dir_name():
    global temp_dir
    if not temp_dir:
        temp_dir = tempfile.TemporaryDirectory(prefix="gtest_gui_tmp")
    return temp_dir.name


def show_trace_snippet(file_name, file_off, length, is_extern_import):
    """
    Display a part of the complete given trace file in the configured external
    trace browser. If the external application can read text via STDIN, the
    text chunk is read from the file and then passed that way. Else, the chunk
    is stored to a temporary file and that file's name is passed on the command
    line. Temporary files are deleted once the external application process
    terminates.
    """
    browser_cmd = config_db.get_opt("log_browser")
    if not browser_cmd:
        StatusLineWidget.get().show_message("error", "No trace browser app is configured")
        return

    if config_db.get_opt("browser_stdin"):
        txt = trace_db.extract_trace(file_name, file_off, length)
        if txt is None:
            StatusLineWidget.get().show_message("error", "Failed to read trace file")
            return
        if txt == "":
            StatusLineWidget.get().show_message("error", "Trace empty for this result")
            return

        file_name = "-"
        shared_file = None

    else:
        file_name = trace_db.extract_trace_to_temp_file(__get_temp_dir_name(),
                                                        file_name, file_off, length,
                                                        is_extern_import)
        if not file_name:
            return
        shared_file = file_name
        txt = ""

    ProcMonitor.create(re.split(r"\s+", browser_cmd) + [file_name], txt, shared_file)


def show_trace(file_name):
    """ Display the complete given trace file in the configured external trace browser. """
    browser_cmd = config_db.get_opt("log_browser")
    if browser_cmd:
        ProcMonitor.create(re.split(r"\s+", browser_cmd) + [file_name], "", None)
    else:
        StatusLineWidget.get().show_message("error", "No trace browser app is configured")


def show_stack_trace(tk_top, tc_name, exe_name, exe_ts, core_name):
    """
    Extract and display a stack trace from the given core file using a simple
    window containing a read-only text frame. Stack trace extraction is done
    using gdb.
    """
    cmd_filename = os.path.join(__get_temp_dir_name(), "gdb_command.bat")
    if not os.path.exists(cmd_filename):
        try:
            with open(cmd_filename, "w", encoding="ascii") as file_obj:
                print("info thread", file=file_obj)
                print("thread apply all backtrace", file=file_obj)
        except OSError as exc:
            msg = "Error writing command input file for gdb: " + str(exc)
            tk_messagebox.showerror(parent=tk_top, message=msg)
            return

    if not exe_name:
        msg = "Executable from which this core originates is unknown. " \
              "Use current executable? Press 'No' to manually select an executable."
        answer = tk_messagebox.askyesnocancel(parent=tk_top, message=msg)
        if answer is None:
            return
        if not answer:
            if os.name == "posix":
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
        exe_file = trace_db.get_exe_file_link_name(exe_name, exe_ts)

    try:
        cmd = ["gdb", "-batch", "-x", cmd_filename, exe_file, core_name]
        # Null device to prevent gdb from getting suspended by SIGTTIN
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, text=True)
        flags = fcntl.fcntl(proc.stdout, fcntl.F_GETFL)
        fcntl.fcntl(proc.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    except (OSError, subprocess.SubprocessError) as exc:
        tk_messagebox.showerror(parent=tk_top, message="Failed to run gdb: " + str(exc))
        return

    title = "GtestGui: Stack trace - %s (%s)" % (tc_name, core_name)
    LogBrowser(tk_top, title, proc)


def export_traces(tk_top, log_idx_sel):
    """
    Export trace file chunks of test results with the given indices from the
    database into an archive file using an external application. The chunks are
    first read and stored in temporary files. A list of names of those files is
    passed to the archiver on the command line. Afterward the files are
    deleted.
    """
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
                txt = trace_db.extract_trace(log[4], log[5], log[6])
                if txt:
                    filename = "trace.%d.%s" % (file_idx, log[0])
                    abs_filename = os.path.join(tempdir, filename)
                    try:
                        with open(abs_filename, "w") as file_obj:
                            file_obj.write(txt)
                    except OSError as exc:
                        tk_messagebox.showerror(
                            parent=tk_top,
                            message="Failed to write temporary file: " + str(exc))
                        break

                    file_list.append(filename)
                    file_idx += 1

        if file_list:
            try:
                cmd = ["zip", "-9", out_name]
                cmd.extend(file_list)
                subprocess.run(cmd, check=True, timeout=20, cwd=tempdir, stdout=subprocess.DEVNULL)
            except (OSError, subprocess.SubprocessError) as exc:
                tk_messagebox.showerror(parent=tk_top,
                                        message="Failed to create archive: " + str(exc))



# ----------------------------------------------------------------------------
#
# Mini dialog only used for displaying text snippets
#

class LogBrowser:
    # This class has no public interfaces as it only interacts via event handlers.
    # pylint: disable=too-few-public-methods
    """
    This class implements a simple top-level window for displaying a read-only
    text that is read from the given subprocess pipe. Text is appended
    dynamically as it is read from the pipe. There is no interaction with
    other application classes.
    """
    def __init__(self, tk_top, title, proc):
        """ Create an instance of the read-only text browser dialog window. """
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

class ProcMonitor:
    """
    Helper class for spawning a process using the given command line and then
    monitoring its status until it exits. After exit, alert the user if exit
    status is non-zero and clean up the given temporary file (if any).
    """
    procs = []
    shared_files = {}
    tid = None

    @staticmethod
    def create(cmd, txt, file_name):
        """ Starts a process with the given command line and then waits for it to finish. """
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if file_name:
                ProcMonitor.alloc_shared_file(file_name)

            ProcMonitor.procs.append(ProcMonitor(proc, txt, file_name))

            if ProcMonitor.tid is None:
                ProcMonitor.tid = tk_utils.tk_top.after(1000, ProcMonitor.proc_monitor)

        except (OSError, subprocess.SubprocessError) as exc:
            tk_messagebox.showerror(parent=tk_utils.tk_top,
                                    message="Failed to start external trace browser: " + str(exc))


    @staticmethod
    def alloc_shared_file(name):
        """
        Internal method for registering a temporary file that may be shared
        with other subprocesses.
        """
        if ProcMonitor.shared_files.get(name, None):
            ProcMonitor.shared_files[name] += 1
        else:
            ProcMonitor.shared_files[name] = 1


    @staticmethod
    def release_shared_file(name):
        """
        Internal method for releasing a temporary file from a process. The file
        is removed if the usage counter drops to zero.
        """
        reg = ProcMonitor.shared_files.get(name, None)
        if reg is not None:
            if reg > 1:
                ProcMonitor.shared_files[name] -= 1
            else:
                del ProcMonitor.shared_files[name]
                try:
                    os.unlink(name)
                except OSError:
                    pass


    @staticmethod
    def remove(proc):
        """
        Internal method for removing a process from the watch list after it
        exited.
        """
        ProcMonitor.procs = [x for x in ProcMonitor.procs if x is not proc]
        if not ProcMonitor.procs and ProcMonitor.tid:
            tk_utils.tk_top.after_cancel(ProcMonitor.tid)
            ProcMonitor.tid = None


    @staticmethod
    def proc_monitor():
        """
        Internal method for adding a process to the watch list. If this is the
        first watched process, a timer is started for periodically checking the
        process' status.
        """
        for proc in ProcMonitor.procs:
            proc.monitor()

        if ProcMonitor.procs:
            ProcMonitor.tid = tk_utils.tk_top.after(1000, ProcMonitor.proc_monitor)
        else:
            ProcMonitor.tid = None


    def __init__(self, proc, txt, file_name):
        self.file_name = file_name
        self.done = False
        self.stderr = None
        self.proc = proc
        self.thr = threading.Thread(target=lambda: self.__thread_browser(txt), daemon=True)
        self.thr.start()


    def __thread_browser(self, txt):
        output = self.proc.communicate(input=txt)

        self.stderr = output[1]
        self.done = True


    def monitor(self):
        """
        Internal method that is called by the class static monitoring timer
        periodically on all instances for monitoring process status. If the
        process has exited, its exit status is checked and an error popup
        displayed for reporting errors to the user. Afterwards possible
        temporary files are cleaned up.
        """
        if self.done:
            if self.proc.returncode != 0:
                msg = "External trace browser reported error code %d: %s" % \
                        (self.proc.returncode, self.stderr)
                tk_messagebox.showerror(parent=tk_utils.tk_top, message=msg)
            if self.file_name:
                ProcMonitor.release_shared_file(self.file_name)
            ProcMonitor.remove(self)

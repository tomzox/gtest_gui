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

import tkinter as tk
from tkinter import messagebox as tk_messagebox
from tkinter import filedialog as tk_filedialog

import gtest_gui.config_db as config_db
import gtest_gui.dlg_config as dlg_config
import gtest_gui.dlg_debug as dlg_debug
import gtest_gui.dlg_font_sel as dlg_font_sel
import gtest_gui.dlg_job_list as dlg_job_list
import gtest_gui.dlg_tc_list as dlg_tc_list
import gtest_gui.gtest as gtest
import gtest_gui.test_db as test_db
import gtest_gui.tk_utils as tk_utils
import gtest_gui.wid_status_line as wid_status_line
import gtest_gui.wid_test_ctrl as wid_test_ctrl
import gtest_gui.wid_test_log as wid_test_log
import gtest_gui.wid_tool_tip as wid_tool_tip


wid_test_ctrl_ = None
wid_test_log_ = None

class Main_window(object):
    def __init__(self, tk_top):
        self.tk = tk_top

        global wid_test_ctrl_
        wid_test_ctrl_ = wid_test_ctrl.Test_control_widget(tk_top, tk_top)
        wid_test_ctrl_.get_widget().pack(side=tk.TOP, fill=tk.BOTH)

        wid_status_line.create_widget(tk_top, wid_test_ctrl_.get_widget())

        global wid_test_log_
        wid_test_log_ = wid_test_log.Test_log_widget(tk_top, tk_top)
        wid_test_log_.get_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        wid_test_log_.set_wid_test_ctrl(wid_test_ctrl_)
        wid_test_ctrl_.set_wid_test_log(wid_test_log_)

        self.create_menubar()

        if test_db.test_exe_name:
            self.update_executable(test_db.test_exe_name)

        wid_test_log_.populate_log()

        # Bindings that apply to all widgets in the main window
        tk_top.bind("<Control-Key-r>", lambda e: wid_test_ctrl_.start_campaign())
        tk_top.bind("<Control-Key-s>", lambda e: wid_test_ctrl_.stop_campaign())
        tk_top.bind("<Control-Key-q>", lambda e: wid_test_ctrl_.resume_campaign())
        tk_top.bind("<Control-Key-t>", lambda e: wid_test_ctrl_.start_repetition())

        tk_top.protocol(name="WM_DELETE_WINDOW", func=self.quit)


    def create_menubar(self):
        wid_men = tk.Menu(self.tk, name="menubar", tearoff=0)
        self.var_opt_test_ctrl = tk.BooleanVar(self.tk, False)
        self.var_opt_tool_tips = tk.BooleanVar(self.tk, config_db.options["enable_tool_tips"])

        wid_tool_tip.enable_tips(config_db.options["enable_tool_tips"])

        wid_men_ctrl = tk.Menu(wid_men, tearoff=0)
        wid_men.add_cascade(menu=wid_men_ctrl, label="Control", underline=0)
        # Included here only for documenting the keyboard shortcut
        wid_men_ctrl.add_command(label="Start tests",
                                 command=wid_test_ctrl_.start_campaign, accelerator="Ctrl-r")
        wid_men_ctrl.add_command(label="Stop tests",    
                                 command=wid_test_ctrl_.stop_campaign, accelerator="Ctrl-s")
        wid_men_ctrl.add_command(label="Resume tests",
                                 command=wid_test_ctrl_.resume_campaign, accelerator="Ctrl-q")
        wid_men_ctrl.add_command(label="Repeat tests",
                                 command=wid_test_ctrl_.start_repetition, accelerator="Ctrl-t")
        wid_men_ctrl.add_separator()
        wid_men_ctrl.add_command(label="Open test case list...",
                                 command=lambda: dlg_tc_list.create_dialog(self.tk, wid_test_ctrl_))
        wid_men_ctrl.add_command(label="Open job list...",
                                 command=lambda: dlg_job_list.create_dialog(self.tk))
        wid_men_ctrl.add_separator()
        wid_men_ctrl.add_command(label="Refresh test case list", command=self.reload_exe)
        wid_men_set_exe = tk.Menu(wid_men_ctrl, tearoff=0, postcommand=self.fill_prev_exe_menu)
        wid_men_ctrl.add_cascade(menu=wid_men_set_exe, label="Select test executable")
        wid_men_set_exe.add_command(label="Select executable file...", command=self.select_exe)
        wid_men_ctrl.add_separator()
        wid_men_ctrl.add_command(label="Quit", command=self.quit)

        wid_men_cfg = tk.Menu(wid_men, tearoff=0)
        wid_men.add_cascade(menu=wid_men_cfg, label="Configure", underline=1)
        wid_men_cfg.add_command(label="Options...",
                                command=lambda: dlg_config.create_dialog(self.tk))
        wid_men_cfg.add_command(label="Font selection...",
                                command=lambda: dlg_font_sel.create_dialog(
                                            self.tk, "wid_test_log",
                                            tk_utils.font_content, wid_test_log_.change_font))
        wid_men_cfg.add_separator()
        wid_men_cfg.add_checkbutton(label="Hide test controls",
                                    command=self.hide_test_ctrl, variable=self.var_opt_test_ctrl)
        wid_men_cfg.add_checkbutton(label="Show tool tip popups",
                                    command=self.toggle_tool_tips, variable=self.var_opt_tool_tips)

        wid_men_log = tk.Menu(wid_men, tearoff=0)
        wid_men.add_cascade(menu=wid_men_log, label="Result log", underline=0)
        wid_test_log_.add_menu_commands(wid_men_log)

        self.tk.eval("option add *Menu.useMotifHelp true")
        wid_men_help = tk.Menu(wid_men, name="help", tearoff=0)
        wid_men.add_cascade(menu=wid_men_help, label="Help", underline=0)
        wid_men_help.add_command(label="Debug console",
                                 command=lambda: dlg_debug.create_dialog(self.tk, globals()))
        wid_men_help.add_command(label="About",
                                 command=self.show_about_dialog)

        self.wid_men_set_exe = wid_men_set_exe
        self.tk.config(menu=wid_men)


    def quit(self):
        if gtest.gtest_ctrl.is_active():
            if not tk_messagebox.askokcancel(parent=self.tk, message="Really stop tests and quit?"):
                return

        config_db.rc_file_update_upon_exit()
        gtest.gtest_ctrl.stop()
        tk_utils.safe_destroy(self.tk)
        return True


    def check_tests_active(self):
        if gtest.gtest_ctrl.is_active():
            msg = "This operation requires stopping ongoing tests."
            if not tk_messagebox.askokcancel(parent=self.tk, message=msg):
                return True
            gtest.gtest_ctrl.stop()
        return False


    def fill_prev_exe_menu(self):
        end_idx = self.wid_men_set_exe.index("end")
        if int(end_idx) > 0:
            self.wid_men_set_exe.delete(1, "end")

        need_sep = True
        for exe_name in reversed(config_db.prev_exe_file_list):
            if exe_name != test_db.test_exe_name:
                if need_sep:
                    self.wid_men_set_exe.add_separator()
                    need_sep = False
                self.wid_men_set_exe.add_command(
                    label=os.path.basename(exe_name),
                    command=lambda path=exe_name: self.select_prev_exe(path))


    def select_exe(self):
        if self.check_tests_active():
            return

        def_name = test_db.test_exe_name
        if not os.path.isfile(def_name):
            def_name = ""

        if (os.name == "posix"):
            filetypes = [("all", "*"), ("Executable", "*.exe")]
        else:
            filetypes = [("Executable", "*.exe"), ("all", "*")]

        filename = tk_filedialog.askopenfilename(
                        parent=self.tk, filetypes=filetypes,
                        title="Select test executable",
                        initialfile=os.path.basename(def_name),
                        initialdir=os.path.dirname(def_name))
        if len(filename) != 0:
            self.update_executable(filename)


    def reload_exe(self):
        if test_db.test_exe_name:
            if self.check_tests_active():
                return

            prev_names = test_db.test_case_names
            self.update_executable(test_db.test_exe_name)

            if test_db.test_case_names:
                if prev_names == test_db.test_case_names:
                    wid_status_line.show_message("warning", "Test case list is unchanged.")
                else:
                    wid_status_line.show_message("info", "New test case list loaded.")
        else:
            self.select_exe()


    def select_prev_exe(self, filename):
        if self.check_tests_active():
            return
        self.update_executable(filename)


    def update_executable(self, filename):
        try:
            exe_ts = int(os.stat(filename).st_mtime)  # cast away sub-second fraction
        except OSError as e:
            tk_messagebox.showerror(parent=self.tk,
                                    message="Failed to access executable: " + str(e))
            return

        tc_names = gtest.gtest_list_tests(exe_file=filename)
        if tc_names is None:
            return

        self.tk.wm_title("GtestGui: " + os.path.basename(filename))
        test_db.update_executable(filename, exe_ts, tc_names)

        config_db.update_prev_exe_file_list(filename)


    def show_about_dialog(self):
        wid_about = tk.Toplevel(self.tk, name="dlg_about")

        wid_about.wm_transient(self.tk)
        wid_about.wm_resizable(1, 1)
        wid_about.wm_group(self.tk)
        wid_about.wm_title("About Gtest GUI")

        wid_lab1 = tk.Label(wid_about, text="Yet another GUI for GoogleTest")
        wid_lab1.pack(side=tk.TOP, pady=8)

        wid_lab2 = tk.Label(wid_about, text="Copyright (C) 2023 Th. Zoerner",
                            font=tk_utils.font_normal)
        wid_lab2.pack(side=tk.TOP)

        msg ="""
Homepage: https://github.com/tomzox/gtest_gui

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
        wid_lab3 = tk.Message(wid_about, font=tk_utils.font_normal, text=msg)
        wid_lab3.pack(side=tk.TOP)

        wid_but = tk.Button(wid_about, text="Close", command=wid_about.destroy)
        wid_but.pack(pady=10)

        wid_but.bind("<Return>", lambda e: e.widget.event_generate("<Key-space>"))
        wid_but.bind("<Escape>", lambda e: e.widget.event_generate("<Key-space>"))
        wid_but.focus_set()


    def hide_test_ctrl(self):
        geom = self.tk.wm_geometry()
        self.tk.wm_geometry(geom)

        if self.var_opt_test_ctrl.get():
            wid_test_log_.toggle_test_ctrl_visible(False)
            wid_test_ctrl_.get_widget().forget()
        else:
            wid_test_log_.toggle_test_ctrl_visible(True)
            wid_test_ctrl_.get_widget().pack(
                side=tk.TOP, fill=tk.BOTH, before=wid_test_log_.get_widget())


    def toggle_tool_tips(self):
        config_db.options["enable_tool_tips"] = self.var_opt_tool_tips.get()
        config_db.rc_file_update_after_idle()

        wid_tool_tip.enable_tips(config_db.options["enable_tool_tips"])

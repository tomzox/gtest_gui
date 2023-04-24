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
from datetime import datetime

import tkinter as tk
from tkinter import messagebox as tk_messagebox
from tkinter import filedialog as tk_filedialog

import gtest_gui.config_db as config_db
import gtest_gui.dlg_config as dlg_config
import gtest_gui.dlg_debug as dlg_debug
import gtest_gui.dlg_font_sel as dlg_font_sel
import gtest_gui.dlg_job_list as dlg_job_list
import gtest_gui.dlg_tc_list as dlg_tc_list
import gtest_gui.dlg_help as dlg_help
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
    def __init__(self, tk_top, exe_name):
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

        self.__create_menubar()

        if exe_name:
            self.__update_executable(exe_name)

        wid_test_log_.populate_log()

        # Bindings that apply to all widgets in the main window
        tk_top.bind("<Control-Key-r>", lambda e: wid_test_ctrl_.start_campaign())
        tk_top.bind("<Control-Key-s>", lambda e: wid_test_ctrl_.stop_campaign())
        tk_top.bind("<Control-Key-q>", lambda e: wid_test_ctrl_.resume_campaign())
        tk_top.bind("<Control-Key-t>", lambda e: wid_test_ctrl_.start_repetition())

        tk_top.protocol(name="WM_DELETE_WINDOW", func=self.quit)


    def __create_menubar(self):
        wid_men = tk.Menu(self.tk, name="menubar", tearoff=0)
        self.var_opt_test_ctrl = tk.BooleanVar(self.tk, True)
        self.var_opt_tool_tips = tk.BooleanVar(self.tk, config_db.options["enable_tool_tips"])

        wid_tool_tip.enable_tips(config_db.options["enable_tool_tips"])

        wid_men_ctrl = wid_tool_tip.Menu(wid_men, tearoff=0)
        wid_men.add_cascade(menu=wid_men_ctrl, label="Control", underline=0)
        # Included here only for documenting the keyboard shortcut
        wid_men_ctrl.add_command(label="Start tests", tooltip="test_ctrl.cmd_start_campaign",
                                 command=wid_test_ctrl_.start_campaign, accelerator="Ctrl-r")
        wid_men_ctrl.add_command(label="Stop tests", tooltip="test_ctrl.cmd_stop_campaign",
                                 command=wid_test_ctrl_.stop_campaign, accelerator="Ctrl-s")
        wid_men_ctrl.add_command(label="Resume tests", tooltip="test_ctrl.cmd_resume_campaign",
                                 command=wid_test_ctrl_.resume_campaign, accelerator="Ctrl-q")
        wid_men_ctrl.add_command(label="Repeat tests", tooltip="test_ctrl.cmd_repeat",
                                 command=wid_test_ctrl_.start_repetition, accelerator="Ctrl-t")
        wid_men_ctrl.add_separator()
        wid_men_ctrl.add_command(label="Open test case list...", tooltip="test_ctrl.cmd_tc_list",
                                 command=lambda: dlg_tc_list.create_dialog(self.tk, wid_test_ctrl_))
        wid_men_ctrl.add_command(label="Open job list...", tooltip="test_ctrl.cmd_job_list",
                                 command=lambda: dlg_job_list.create_dialog(self.tk))
        wid_men_ctrl.add_separator()
        wid_men_ctrl.add_command(label="Refresh test case list", tooltip="test_ctrl.cmd_refresh",
                                 command=self.reload_exe)
        wid_men_set_exe = wid_tool_tip.Menu(wid_men_ctrl, tearoff=0,
                                            postcommand=self.__fill_prev_exe_menu)
        wid_men_ctrl.add_cascade(menu=wid_men_set_exe, label="Select test executable")
        wid_men_set_exe.add_command(label="Select executable file...", command=self.select_exe)
        wid_men_ctrl.add_separator()
        wid_men_ctrl.add_command(label="Quit", command=self.quit)

        wid_men_cfg = wid_tool_tip.Menu(wid_men, tearoff=0)
        wid_men.add_cascade(menu=wid_men_cfg, label="Configure", underline=1)
        wid_men_cfg.add_command(label="Options...",
                                command=lambda: dlg_config.create_dialog(self.tk))
        wid_men_cfg.add_separator()
        wid_men_cfg.add_command(label="Select font for result log...",
                                tooltip="config.select_font_content",
                                command=lambda: dlg_font_sel.create_dialog(
                                            self.tk, "content",
                                            tk_utils.font_content, self.__change_font))
        wid_men_cfg.add_command(label="Select font for trace preview...",
                                tooltip="config.select_font_trace",
                                command=lambda: dlg_font_sel.create_dialog(
                                            self.tk, "trace",
                                            tk_utils.font_trace, self.__change_font))
        wid_men_cfg.add_separator()
        wid_men_cfg.add_checkbutton(label="Show test controls", tooltip="config.show_controls",
                                    command=self.show_test_ctrl, variable=self.var_opt_test_ctrl)
        wid_men_cfg.add_checkbutton(label="Show tool tip popups", tooltip="config.show_tool_tips",
                                    command=self.toggle_tool_tips, variable=self.var_opt_tool_tips)

        wid_men_log = wid_tool_tip.Menu(wid_men, tearoff=0)
        wid_men.add_cascade(menu=wid_men_log, label="Result log", underline=0)
        wid_test_log_.add_menu_commands(wid_men_log)

        self.tk.eval("option add *Menu.useMotifHelp true")
        wid_men_help = tk.Menu(wid_men, name="help", tearoff=0)
        wid_men.add_cascade(menu=wid_men_help, label="Help", underline=0)
        dlg_help.add_menu_commands(self.tk, wid_men_help)
        wid_men_help.add_separator()
        wid_men_help.add_command(label="Debug console",
                                 command=lambda: dlg_debug.create_dialog(self.tk, globals()))
        wid_men_help.add_command(label="About",
                                 command=self.show_about_dialog)

        self.var_prev_exe_name = tk.StringVar(self.tk, "")
        self.wid_men_set_exe = wid_men_set_exe
        self.tk.config(menu=wid_men)


    def quit(self):
        if gtest.gtest_ctrl.is_active():
            if not tk_messagebox.askokcancel(parent=self.tk, message="Really stop tests and quit?"):
                return

        config_db.rc_file_update_upon_exit()
        gtest.gtest_ctrl.stop(kill=True)
        gtest.release_exe_file_copy()
        if config_db.options["exit_clean_trace"]:
            gtest.clean_all_trace_files()

        tk_utils.safe_destroy(self.tk)
        return True


    def __check_tests_active(self):
        if gtest.gtest_ctrl.is_active():
            msg = "This operation requires stopping ongoing tests."
            if not tk_messagebox.askokcancel(parent=self.tk, message=msg):
                return True
            gtest.gtest_ctrl.stop(kill=True)
        return False


    def __change_font(self, foo):
        tk_utils.update_derived_fonts()
        config_db.rc_file_update()


    @staticmethod
    def __get_unique_prev_exe_name(input_paths, mapped):
        # Build reverse list of path elements: split at separators
        input_paths = sorted(input_paths)
        path_lists = []
        for path in input_paths:
            path_list = []
            while path:
                p1, p2 = os.path.split(path)
                if not p2 or p1 == os.path.sep:
                    path_list.append(path)
                    break
                path_list.append(p2)
                path = p1

            path_lists.append(path_list)

        # Determine indices where paths differ
        delta_sets = [set() for x in path_lists]
        for idx1 in range(len(path_lists) - 1):
            prev_path_list = path_lists[idx1]
            idx2 = 0
            for path_list in path_lists[idx1:]:
                for idx in range(0, len(path_list)):
                    if idx >= len(prev_path_list):
                        delta_sets[idx2].add(idx)
                        break
                    elif path_list[idx] != prev_path_list[idx]:
                        delta_sets[idx1].add(idx)
                        delta_sets[idx2].add(idx)
                        break
                idx2 += 1

        # Reassemble paths, while skipping equal elements
        idx1 = 0
        for path_list in path_lists:
            delta_set = delta_sets[idx1]
            delta_set.add(0)

            prev_skip = False
            new_path_list = []
            for idx in reversed(range(len(path_list))):
                if idx in delta_set:
                    if prev_skip and new_path_list:
                        new_path_list.append("...")
                    new_path_list.append(path_list[idx])
                    prev_skip = False
                else:
                    prev_skip = True

            mapped[input_paths[idx1]] = os.path.join(*new_path_list)
            idx1 += 1


    @staticmethod
    def __get_prev_exe_names(exe_names):
        base_names = {}
        for exe_name in exe_names:
            base = os.path.basename(exe_name)
            if base_names.get(base) is None:
                base_names[os.path.basename(exe_name)] = [exe_name]
            else:
                base_names[os.path.basename(exe_name)].append(exe_name)

        mapped = {}
        for base_name, paths in base_names.items():
            if len(paths) > 1:
                Main_window.__get_unique_prev_exe_name(paths, mapped)
            else:
                mapped[paths[0]] = os.path.basename(paths[0])

        return mapped


    def __fill_prev_exe_menu(self):
        end_idx = self.wid_men_set_exe.index("end")
        if int(end_idx) > 0:
            self.wid_men_set_exe.delete(1, "end")

        self.var_prev_exe_name.set(test_db.test_exe_name)

        mapped = Main_window.__get_prev_exe_names(config_db.prev_exe_file_list)
        need_sep = True
        for exe_name in reversed(config_db.prev_exe_file_list):
            if need_sep:
                self.wid_men_set_exe.add_separator()
                need_sep = False

            tip_text = exe_name + "\n"
            try:
                exe_ts = os.stat(exe_name).st_mtime
                # RFC 2822-compliant date format
                tip_text += datetime.fromtimestamp(exe_ts).strftime("Timestamp: %a, %d %b %Y %T %z")
                state = tk.NORMAL
            except OSError as e:
                tip_text += "File not found"
                state = tk.DISABLED

            self.wid_men_set_exe.add_radiobutton(
                label=mapped[exe_name], state=state,
                variable=self.var_prev_exe_name, value=exe_name,
                tooltip=lambda tip_text=tip_text: tip_text,
                command=lambda path=exe_name: self.__select_prev_exe(path))


    def select_exe(self):
        if self.__check_tests_active():
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
        if filename:
            self.__update_executable(filename)


    def reload_exe(self):
        if self.__check_tests_active():
            return

        if test_db.test_exe_name:
            self.__update_executable(test_db.test_exe_name)
        else:
            self.select_exe()


    def __select_prev_exe(self, filename):
        if self.__check_tests_active():
            return
        self.__update_executable(filename)


    def __update_executable(self, filename):
        try:
            exe_ts = int(os.stat(filename).st_mtime)  # cast away sub-second fraction
        except OSError as e:
            tk_messagebox.showerror(parent=self.tk,
                                    message="Failed to access executable: " + str(e))
            return

        prev_exe = test_db.test_exe_name
        prev_names = test_db.test_case_names

        tc_names = gtest.gtest_list_tests(exe_file=filename)
        if tc_names is None:
            return

        if filename != test_db.test_exe_name:
            self.tk.wm_title("GtestGui: " + os.path.basename(filename))
            gtest.release_exe_file_copy()
            test_db.update_executable(filename, exe_ts, tc_names)

            config_db.update_prev_exe_file_list(filename)

        if prev_exe: # no message during startup
            if prev_exe != filename:
                wid_status_line.show_message("info", "Switched to new executable.")
            elif prev_names != test_db.test_case_names:
                wid_status_line.show_message("info", "New test case list loaded.")
            else:
                wid_status_line.show_message("warning", "Test case list is unchanged.")


    def show_about_dialog(self):
        wid_about = tk.Toplevel(self.tk, name="dlg_about")

        wid_about.wm_transient(self.tk)
        wid_about.wm_resizable(1, 1)
        wid_about.wm_group(self.tk)
        wid_about.wm_title("About Gtest GUI")

        wid_lab1 = tk.Label(wid_about, text="Module tester's GoogleTest GUI",
                            font=tk_utils.font_bold)
        wid_lab1.pack(side=tk.TOP, pady=5)

        wid_lab2 = tk.Label(wid_about, text="Version 0.8.1\n"
                                            "Copyright (C) 2023 T. Zoerner")
        wid_lab2.pack(side=tk.TOP)

        url = "https://github.com/tomzox/gtest_gui"
        wid_lab3 = tk.Label(wid_about, text=url, fg="blue",
                            cursor="top_left_arrow")
        wid_lab3.pack(side=tk.TOP, pady=5)

        msg ="""
This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
        wid_lab4 = tk.Message(wid_about, font=tk_utils.font_normal, text=msg)
        wid_lab4.pack(side=tk.TOP)

        wid_but = tk.Button(wid_about, text="Close", command=wid_about.destroy)
        wid_but.pack(pady=10)

        wid_but.bind("<Return>", lambda e: e.widget.event_generate("<Key-space>"))
        wid_but.bind("<Escape>", lambda e: e.widget.event_generate("<Key-space>"))
        wid_lab3.bind("<ButtonRelease-1>", lambda e: tk_utils.xselection_export(url, True))
        wid_but.focus_set()


    def show_test_ctrl(self):
        geom = self.tk.wm_geometry()
        self.tk.wm_geometry(geom)

        if self.var_opt_test_ctrl.get():
            wid_test_log_.toggle_test_ctrl_visible(True)
            wid_test_ctrl_.get_widget().pack(
                side=tk.TOP, fill=tk.BOTH, before=wid_test_log_.get_widget())
        else:
            wid_test_log_.toggle_test_ctrl_visible(False)
            wid_test_ctrl_.get_widget().forget()


    def toggle_tool_tips(self):
        config_db.options["enable_tool_tips"] = self.var_opt_tool_tips.get()
        config_db.rc_file_update_after_idle()

        wid_tool_tip.enable_tips(config_db.options["enable_tool_tips"])

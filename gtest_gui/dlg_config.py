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

#
# This class implements the configuration parameter dialog.
#

import os
import re
import tkinter as tk
from tkinter import messagebox as tk_messagebox
from tkinter import filedialog as tk_filedialog

import gtest_gui.config_db as config_db
import gtest_gui.gtest as gtest
import gtest_gui.tk_utils as tk_utils
import gtest_gui.wid_tool_tip as wid_tool_tip

prev_dialog_wid = None

def create_dialog(tk_top):
    global prev_dialog_wid

    if prev_dialog_wid and tk_utils.wid_exists(prev_dialog_wid.wid_top):
        prev_dialog_wid.raise_window()
    else:
        prev_dialog_wid = Config_dialog(tk_top)


class Config_dialog(object):
    def __init__(self, tk_top):
        self.tk = tk_top
        self.var_cfg_browser = tk.StringVar(tk_top, config_db.options["browser"])
        self.var_cfg_browser_stdin = tk.BooleanVar(tk_top, config_db.options["browser_stdin"])
        self.var_cfg_seed_regexp = tk.StringVar(tk_top, config_db.options["seed_regexp"])

        self.var_cfg_trace_dir = tk.StringVar(tk_top, config_db.options["trace_dir"])
        self.var_cfg_exit_clean_trace = tk.BooleanVar(tk_top, config_db.options["exit_clean_trace"])
        self.var_cfg_startup_import = tk.BooleanVar(tk_top, config_db.options["startup_import_trace"])
        self.var_cfg_copy_executable = tk.BooleanVar(tk_top, config_db.options["copy_executable"])

        self.var_cfg_valgrind1 = tk.StringVar(tk_top, config_db.options["valgrind1"])
        self.var_cfg_valgrind2 = tk.StringVar(tk_top, config_db.options["valgrind2"])
        self.var_cfg_valgrind_exit = tk.BooleanVar(tk_top, config_db.options["valgrind_exit"])

        self.wid_top = tk.Toplevel(tk_top)
        self.wid_top.wm_group(tk_top)
        self.wid_top.wm_title("GtestGui: Configuration options")

        self.wid_top.columnconfigure(1, weight=1)

        self.__add_entry_widget(0, "Trace browser:", self.var_cfg_browser, "config.trowser")
        self.__add_checkbutton(1, 'Browser supports reading from STDIN with file name "-"',
                               self.var_cfg_browser_stdin, "config.trowser_stdin")
        self.__add_entry_widget(2, "Pattern for seed:", self.var_cfg_seed_regexp, "config.seed")
        self.__add_separator(3)

        self.__add_entry_with_button(4, "Directory for trace files:", self.var_cfg_trace_dir,
                                     self.__open_trace_dir_file_browser, "config.trace_dir")
        self.__add_checkbutton(5, "Automatically remove trace files of passed tests upon exit",
                               self.var_cfg_exit_clean_trace, "config.exit_clean_trace")
        self.__add_checkbutton(6, "Automatically import trace files upon start",
                               self.var_cfg_startup_import, "config.startup_import_trace")
        self.__add_checkbutton(7, "Create copy of executable file under test",
                               self.var_cfg_copy_executable, "config.copy_executable")
        self.__add_separator(8)

        self.__add_entry_widget(9, "Valgrind command line:", self.var_cfg_valgrind1, "config.valgrind1")
        self.__add_entry_widget(10, "Valgrind alternate:", self.var_cfg_valgrind2, "config.valgrind2")
        self.__add_checkbutton(11, "Valgrind supports --error-exitcode",
                               self.var_cfg_valgrind_exit, "config.valgrind_exit")

        wid_frm = tk.Frame(self.wid_top)
        wid_but_abort = tk.Button(wid_frm, text="Cancel", command=self.__quit)
        wid_but_abort.pack(side=tk.LEFT, padx=10)
        wid_but_apply = tk.Button(wid_frm, text="Apply", command=self.__apply_config)
        wid_but_apply.pack(side=tk.LEFT, padx=10)
        wid_but_ok = tk.Button(wid_frm, text="Ok", command=self.__save_and_close)
        wid_but_ok.pack(side=tk.LEFT, padx=10)
        wid_frm.grid(row=12, columnspan=2, pady=10)

        wid_but_ok.bind("<Escape>", lambda e: self.__quit())
        wid_but_ok.bind("<Return>", lambda e: self.__save_and_close())
        wid_but_ok.focus_set()

        wid_frm.bind("<Destroy>", lambda e: self.__quit())


    def __add_entry_widget(self, grid_row, text, cfg_var, tip_key):
        wid_lab = tk.Label(self.wid_top, text=text)
        wid_lab.grid(row=grid_row, column=0, sticky="e")
        wid_val = tk.Entry(self.wid_top, textvariable=cfg_var, width=60)
        wid_val.grid(row=grid_row, column=1, sticky="we", padx=5, pady=2)
        wid_tool_tip.tool_tip_add(wid_lab, tip_key)


    def __add_entry_with_button(self, grid_row, text, cfg_var, cfg_cmd, tip_key):
        wid_lab = tk.Label(self.wid_top, text=text)
        wid_lab.grid(row=grid_row, column=0, sticky="e")
        wid_tool_tip.tool_tip_add(wid_lab, tip_key)

        wid_frm = tk.Frame(self.wid_top, relief=tk.SUNKEN, borderwidth=1)
        wid_val = tk.Entry(wid_frm, textvariable=cfg_var, relief=tk.FLAT, borderwidth=0)
        wid_val.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

        wid_but = tk.Button(wid_frm, image="img_folder", takefocus=0, borderwidth=1,
                            relief=tk.RAISED, highlightthickness=1, command=cfg_cmd)
        wid_but.pack(side=tk.LEFT, fill=tk.Y)
        wid_frm.grid(row=grid_row, column=1, sticky="we", padx=5, pady=2)


    def __add_checkbutton(self, grid_row, text, cfg_var, tip_key):
        wid_val = tk.Checkbutton(self.wid_top, text=text, variable=cfg_var)
        wid_val.grid(row=grid_row, column=1, sticky="w", padx=5, pady=2)
        wid_tool_tip.tool_tip_add(wid_val, tip_key)


    def __add_separator(self, grid_row):
        wid_sep = tk.Frame(self.wid_top, borderwidth=1, relief=tk.SUNKEN, height=2)
        wid_sep.grid(row=grid_row, column=0, columnspan=2, sticky="we", padx=0, pady=5)


    def raise_window(self):
        self.wid_top.wm_deiconify()
        self.wid_top.lift()


    def __quit(self):
        global prev_dialog_wid
        tk_utils.safe_destroy(self.wid_top)
        prev_dialog_wid = None


    def __open_trace_dir_file_browser(self):
        dirname = tk_filedialog.askdirectory(
                        parent=self.wid_top, title="Select trace directory",
                        initialdir=self.var_cfg_trace_dir.get())
        if dirname:
            self.var_cfg_trace_dir.set(dirname)


    def __check_seed_pattern(self, seed_exp):
        try:
            re.compile(seed_exp)
        except Exception as e:
            tk_messagebox.showerror(
                    parent=self.wid_top,
                    message="Syntax error in regular expression for \"seed\": " + str(e))
            return False
        return True


    def __check_trace_dir(self, trace_dir):
        if not os.path.isdir(trace_dir):
            if os.path.exists(trace_dir):
                tk_messagebox.showerror(parent=self.wid_top,
                                        message="Trace directory is not a directory")
                return False

            if not tk_messagebox.askokcancel(
                        parent=self.wid_top,
                        message="Trace directory does not exist - Do you want to create it?"):
                return False

            try:
                os.mkdir(trace_dir)
            except OSError as e:
                tk_messagebox.showerror(parent=self.wid_top,
                                        message="Failed to create directory: " + str(e))
                return False

        return True


    def __apply_config(self):
        seed_exp = self.var_cfg_seed_regexp.get()
        if seed_exp and not self.__check_seed_pattern(seed_exp):
            return False

        trace_dir = self.var_cfg_trace_dir.get().strip()
        if trace_dir:
            trace_dir = os.path.abspath(trace_dir)
            if not self.__check_trace_dir(trace_dir):
                return False

        if ((trace_dir != config_db.options["trace_dir"]) or
            (self.var_cfg_copy_executable.get() != config_db.options["copy_executable"])):
            if gtest.gtest_ctrl.is_active():
                msg = "Need to stop running tests for changing the trace directory " \
                      "or copy-executable options."
                if not tk_messagebox.askokcancel(parent=self.wid_top, message=msg):
                    return False
                gtest.gtest_ctrl.stop(kill=True)

            gtest.release_exe_file_copy()

        config_db.options["browser"] = re.sub(r"\s+", " ", self.var_cfg_browser.get()).strip()
        config_db.options["browser_stdin"] = self.var_cfg_browser_stdin.get()
        config_db.options["seed_regexp"] = seed_exp

        config_db.options["trace_dir"] = trace_dir
        config_db.options["exit_clean_trace"] = self.var_cfg_exit_clean_trace.get()
        config_db.options["startup_import_trace"] = self.var_cfg_startup_import.get()
        config_db.options["copy_executable"] = self.var_cfg_copy_executable.get()

        config_db.options["valgrind1"] = re.sub(r"\s+", " ", self.var_cfg_valgrind1.get()).strip()
        config_db.options["valgrind2"] = re.sub(r"\s+", " ", self.var_cfg_valgrind2.get()).strip()
        config_db.options["valgrind_exit"] = self.var_cfg_valgrind_exit.get()

        return config_db.rc_file_update()


    def __save_and_close(self):
        if self.__apply_config():
            self.__quit()

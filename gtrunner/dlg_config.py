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

import re
import tkinter as tk
from tkinter import messagebox as tk_messagebox

import gtrunner.config_db as config_db
import gtrunner.tk_utils as tk_utils
import gtrunner.wid_tool_tip as wid_tool_tip

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
        self.var_cfg_valgrind1 = tk.StringVar(tk_top, config_db.options["valgrind1"])
        self.var_cfg_valgrind2 = tk.StringVar(tk_top, config_db.options["valgrind2"])
        self.var_cfg_valgrind_exit = tk.BooleanVar(tk_top, config_db.options["valgrind_exit"])

        self.wid_top = tk.Toplevel(tk_top)
        self.wid_top.wm_group(tk_top)
        self.wid_top.wm_title("Configure gtrunner")

        self.wid_top.columnconfigure(1, weight=1)

        self.add_entry_widget(0, "Trace browser:", self.var_cfg_browser, "config.trowser")
        self.add_checkbutton(1, 'Browser supports reading from STDIN with file name "-"',
                             self.var_cfg_browser_stdin, "config.trowser_stdin")
        self.add_entry_widget(2, "Pattern for seed:", self.var_cfg_seed_regexp, "config.seed")
        self.add_entry_widget(3, "Valgrind command line:", self.var_cfg_valgrind1, "config.valgrind1")
        self.add_entry_widget(4, "Valgrind alternate:", self.var_cfg_valgrind2, "config.valgrind2")
        self.add_checkbutton(5, "Valgrind supports --error-exitcode",
                             self.var_cfg_valgrind_exit, "config.valgrind_exit")

        wid_frm = tk.Frame(self.wid_top)
        wid_but_abort = tk.Button(wid_frm, text="Cancel", command=self.quit)
        wid_but_abort.pack(side=tk.LEFT, padx=10)
        wid_but_apply = tk.Button(wid_frm, text="Apply", command=self.apply_config)
        wid_but_apply.pack(side=tk.LEFT, padx=10)
        wid_but_ok = tk.Button(wid_frm, text="Ok", command=self.save_and_close)
        wid_but_ok.pack(side=tk.LEFT, padx=10)
        wid_frm.grid(row=6, columnspan=2, pady=10)

        wid_but_ok.bind("<Escape>", lambda e: self.quit())
        wid_but_ok.bind("<Return>", lambda e: self.save_and_close())
        wid_but_ok.focus_set()

        wid_frm.bind("<Destroy>", lambda e: self.quit())


    def add_entry_widget(self, grid_row, text, cfg_var, tip_key):
        wid_lab = tk.Label(self.wid_top, text=text)
        wid_lab.grid(row=grid_row, column=0, sticky="e")
        wid_val = tk.Entry(self.wid_top, textvariable=cfg_var, width=60)
        wid_val.grid(row=grid_row, column=1, sticky="we", padx=5, pady=2)
        wid_tool_tip.tool_tip_add(wid_lab, tip_key)


    def add_checkbutton(self, grid_row, text, cfg_var, tip_key):
        wid_val = tk.Checkbutton(self.wid_top, text=text, variable=cfg_var)
        wid_val.grid(row=grid_row, column=1, sticky="w", padx=5, pady=2)
        wid_tool_tip.tool_tip_add(wid_val, tip_key)


    def raise_window(self):
        self.wid_top.wm_deiconify()
        self.wid_top.lift()


    def quit(self):
        global prev_dialog_wid
        tk_utils.safe_destroy(self.wid_top)
        prev_dialog_wid = None


    def apply_config(self):
        seed_exp = self.var_cfg_seed_regexp.get()
        try:
            re.compile(seed_exp)
        except Exception as e:
            tk_messagebox.showerror(parent=self.wid_top,
                          message="Syntax error in regular expression for \"seed\": " + str(e))
            return False

        config_db.options["browser"] = re.sub(r"\s+", " ", self.var_cfg_browser.get()).strip()
        config_db.options["browser_stdin"] = self.var_cfg_browser_stdin.get()
        config_db.options["seed_regexp"] = self.var_cfg_seed_regexp.get()
        config_db.options["valgrind1"] = re.sub(r"\s+", " ", self.var_cfg_valgrind1.get()).strip()
        config_db.options["valgrind2"] = re.sub(r"\s+", " ", self.var_cfg_valgrind2.get()).strip()
        config_db.options["valgrind_exit"] = self.var_cfg_valgrind_exit.get()

        return config_db.rc_file_update()


    def save_and_close(self):
        if self.apply_config():
            self.quit()

#!/usr/bin/env python3

# ------------------------------------------------------------------------ #
# Copyright (C) 2007-2010,2019-2023 Th. Zoerner
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

# This code is derived from Trace Browser (trowser.py)

import tkinter as tk
import tkinter.font as tkf

import gtest_gui.tk_utils as tk_utils

prev_dialog_wid = {}

def create_dialog(tk_top, ftype, font, callback):
    global prev_dialog_wid

    if prev_dialog_wid.get(ftype, None) and tk_utils.wid_exists(prev_dialog_wid[ftype].wid_top):
        prev_dialog_wid[ftype].raise_window()
    else:
        prev_dialog_wid[ftype] = Font_selection_dialog(tk_top, ftype, font, callback)


class Font_selection_dialog(object):
    def __init__(self, tk_top, ftype, font, callback):
        self.tk = tk_top
        self.ftype = ftype
        self.font = font
        self.callback = callback

        self.wid_top = tk.Toplevel(self.tk)
        self.wid_top.wm_title("GtestGui: Font selection")
        self.wid_top.wm_group(self.tk)

        self.var_font_bold = tk.BooleanVar(self.tk, False)
        self.var_font_size = tk.IntVar(self.tk, 10)

        # frame #1: listbox with all available fonts
        wid_frm = tk.Frame(self.wid_top)
        self.wid_font_list = tk.Listbox(wid_frm, width=40, height=10, font=tk_utils.font_normal,
                                        exportselection=0, cursor="top_left_arrow",
                                        selectmode=tk.BROWSE)
        self.wid_font_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        wid_sb = tk.Scrollbar(wid_frm, orient=tk.VERTICAL, command=self.wid_font_list.yview,
                              takefocus=0)
        wid_sb.pack(side=tk.LEFT, fill=tk.Y)
        self.wid_font_list.configure(yscrollcommand=wid_sb.set)
        wid_frm.pack(side=tk.TOP, fill=tk.BOTH, expand=1, padx=5, pady=5)
        self.wid_font_list.bind("<<ListboxSelect>>",
                                lambda e: tk_utils.bind_call_and_break(
                                            self.__handle_selection_change))

        # frame #2: size and weight controls
        wid_frm2 = tk.Frame(self.wid_top)
        wid_lab = tk.Label(wid_frm2, text="Font size:")
        wid_lab.pack(side=tk.LEFT)
        wid_spin = tk.Spinbox(wid_frm2, from_=1, to=99, width=3,
                              textvariable=self.var_font_size, command=self.__handle_selection_change)
        wid_spin.pack(side=tk.LEFT)
        wid_chk = tk.Checkbutton(wid_frm2, text="bold",
                                 variable=self.var_font_bold, command=self.__handle_selection_change)
        wid_chk.pack(side=tk.LEFT, padx=15)
        wid_frm2.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # frame #3: demo text
        self.wid_demo = tk.Text(self.wid_top, width=20, height=4, wrap=tk.NONE,
                                exportselection=tk.FALSE, relief=tk.RIDGE, takefocus=0)
        self.wid_demo.pack(side=tk.TOP, fill=tk.X, padx=15, pady=10)
        self.wid_demo.bindtags([self.wid_demo, "TextReadOnly", self.tk, "all"])

        self.wid_demo.insert("end", "ABCDEFGHIJKLMNOPQRSTUVWXYZ\n")
        self.wid_demo.insert("end", "abcdefghijklmnopqrstuvwxyz\n")
        self.wid_demo.insert("end", "0123456789\n")
        self.wid_demo.insert("end", "AAA ,,,...---;;;:::___+++=== AAA\n")

        # frame #4: ok/abort buttons
        wid_frm3 = tk.Frame(self.wid_top)
        wid_but_cancel = tk.Button(wid_frm3, text="Abort", command=self.__quit)
        wid_but_apply = tk.Button(wid_frm3, text="Apply", command=self.__apply_config)
        wid_but_ok = tk.Button(wid_frm3, text="Ok", default=tk.ACTIVE,
                               command=self.__save_and_close)
        wid_but_cancel.pack(side=tk.LEFT, padx=10, pady=5)
        wid_but_apply.pack(side=tk.LEFT, padx=10, pady=5)
        wid_but_ok.pack(side=tk.LEFT, padx=10, pady=5)
        wid_frm3.pack(side=tk.TOP)

        wid_frm.bind("<Destroy>", lambda e: self.__quit())
        wid_but_ok.bind("<Return>", lambda e: wid_but_ok.event_generate("<space>"))
        self.wid_top.bind("<Escape>", lambda e: wid_but_cancel.event_generate("<space>"))
        self.wid_font_list.focus_set()

        # fill font list and select current font
        self.__fill_font_list()
        self.var_font_bold.set(self.font.cget("weight") != "normal")
        self.var_font_size.set(self.font.cget("size"))
        cur_fam = self.font.cget("family")
        try:
            idx = self.font_families.index(cur_fam)  # raises ValueError if not found
            self.wid_font_list.activate(idx)
            self.wid_font_list.selection_set(idx)
            self.wid_font_list.see(idx)
        except ValueError:
            pass

        # finally update demo box with the currently selected font
        self.__handle_selection_change()


    def raise_window(self):
        self.wid_top.wm_deiconify()
        self.wid_top.lift()
        self.wid_font_list.focus_set()


    def __fill_font_list(self):
        # remove duplicates, then sort alphabetically
        self.font_families = sorted(set(tkf.families(displayof=self.tk)))

        for f in self.font_families:
            self.wid_font_list.insert("end", f)


    def __handle_selection_change(self):
        sel = self.wid_font_list.curselection()
        if (len(sel) == 1) and (sel[0] < len(self.font_families)):
          name = "{%s} %d" % (self.font_families[sel[0]], self.var_font_size.get())
          if self.var_font_bold.get():
              name = name + " bold"

          # succeeds even for unknown fonts, therefore try/except not needed
          self.wid_demo.configure(font=name)


    def __quit(self):
        tk_utils.safe_destroy(self.wid_top)
        prev_dialog_wid.pop(self.ftype, None)


    def __apply_config(self):
        sel = self.wid_font_list.curselection()
        if (len(sel) == 1) and (sel[0] < len(self.font_families)):
            self.font.configure(family=self.font_families[sel[0]],
                                size=self.var_font_size.get(),
                                weight=(tkf.BOLD if self.var_font_bold.get() else tkf.NORMAL))
            try:
                self.callback(self.font)
                return True

            except Exception as e:
                tk.messagebox.showerror(parent=self.wid_top,
                                        message="Selected font is unavailable: " + str(e))
        else:
            tk.messagebox.showerror(parent=self.wid_top,
                                    message=("No font is selected - "
                                             "Use \"Abort\" to leave without changes."))
        return False


    def __save_and_close(self):
        if self.__apply_config():
            self.__quit()

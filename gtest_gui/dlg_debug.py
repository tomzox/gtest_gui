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

import re
import tkinter as tk

import gtest_gui.tk_utils as tk_utils
import gtest_gui.wid_tool_tip as wid_tool_tip

prev_dialog_wid = None

def create_dialog(tk_top, main_globals, raise_if_exists=True):
    global prev_dialog_wid

    if (raise_if_exists
            and prev_dialog_wid
            and tk_utils.wid_exists(prev_dialog_wid.get_toplevel())):
        prev_dialog_wid.raise_window()
    else:
        prev_dialog_wid = Debug_dialog(tk_top, main_globals)


class Debug_dialog(object):
    def __init__(self, tk_top, main_globals):
        self.tk = tk_top
        self.globals = main_globals
        self.wid_top = tk.Toplevel(self.tk)
        self.wid_top.wm_group(self.tk)
        self.wid_top.wm_title("GtestGui: Debug console")

        char_h = self.tk.call("font", "metrics", "TkFixedFont", "-linespace")
        height = 15 * char_h

        self.__create_var_name_entry_frame(self.wid_top)

        wid_pane = tk.PanedWindow(self.wid_top, orient=tk.VERTICAL,
                                  sashrelief=tk.RAISED, showhandle=1, sashpad=4)
        wid_pane.pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        self.__create_output_frame(wid_pane)
        self.__create_input_frame(wid_pane, height)
        self.wid_input.focus_set()

        self.__create_command_frame(self.wid_top)


    def raise_window(self):
        self.wid_top.wm_deiconify()
        self.wid_top.lift()


    def get_toplevel(self):
        return self.wid_top


    def __create_var_name_entry_frame(self, wid_parent):
        wid_frm = tk.Frame(wid_parent, padx=1, pady=2)
        wid_lab = tk.Label(wid_frm, text="Name:")
        wid_lab.pack(side=tk.LEFT, pady=2)
        wid_ent = tk.Entry(wid_frm)
        wid_ent.pack(side=tk.LEFT, fill=tk.X, expand=1)
        wid_but = tk.Button(wid_frm, text="Lookup", padx=5, pady=1,
                            command=lambda: self.__show_variable_value(True))
        wid_but.pack(side=tk.LEFT)
        wid_tool_tip.tool_tip_add(wid_but, "debug.lookup")
        wid_frm.pack(side=tk.TOP, fill=tk.X)
        self.wid_var_name = wid_ent


    def __create_output_frame(self, wid_pane):
        wid_frm = tk.LabelFrame(wid_pane, text="Output")
        wid_txt = tk.Text(wid_frm, width=80, height=5, wrap=tk.CHAR, relief=tk.FLAT, borderwidth=0,
                          exportselection=1, font="TkFixedFont", cursor="top_left_arrow")
        wid_txt.bindtags([wid_txt, "TextReadOnly", self.wid_top, "all"])
        wid_txt.tag_configure("var_name", foreground="blue")
        wid_txt.tag_bind("var_name", "<ButtonRelease-1>",
                         lambda e: self.__show_tagged_variable(e.x, e.y))
        wid_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        wid_sb = tk.Scrollbar(wid_frm, orient=tk.VERTICAL, command=wid_txt.yview, takefocus=0)
        wid_sb.pack(side=tk.LEFT, fill=tk.BOTH)
        wid_txt.configure(yscrollcommand=wid_sb.set)

        wid_pane.add(wid_frm, sticky="news", stretch="always")
        self.wid_output = wid_txt


    def __create_input_frame(self, wid_pane, height):
        wid_frm = tk.LabelFrame(wid_pane, text="Input")
        wid_txt = tk.Text(wid_frm, width=80, height=10, undo=1, maxundo=500, wrap=tk.CHAR,
                          autoseparators=1, font="TkFixedFont", exportselection=1, relief=tk.FLAT,
                          borderwidth=0)
        wid_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        wid_sb = tk.Scrollbar(wid_frm, orient=tk.VERTICAL, command=wid_txt.yview, takefocus=0)
        wid_sb.pack(side=tk.LEFT, fill=tk.Y)
        wid_txt.configure(yscrollcommand=wid_sb.set)

        wid_txt.bind("<Control-Key-e>", lambda e: tk_utils.bind_call_and_break(
                                                    lambda: self.__eval_input(False)))
        wid_txt.bind("<Control-Key-x>", lambda e: tk_utils.bind_call_and_break(
                                                    lambda: self.__eval_input(True)))
        wid_txt.bind("<Key-Tab>", wid_txt.bind("Text", "<Control-Key-Tab>"))

        wid_pane.add(wid_frm, sticky="news", height=height)
        self.wid_input = wid_txt


    def __create_command_frame(self, wid_parent):
        wid_frm = tk.Frame(wid_parent)
        wid_but_eval = tk.Button(wid_frm, text="Eval", width=5, underline=0,
                                 pady=1, command=lambda: self.__eval_input(False))
        wid_but_exec = tk.Button(wid_frm, text="Exec", width=5, underline=1,
                                 pady=1, command=lambda: self.__eval_input(True))
        wid_but_clear = tk.Button(wid_frm, text="Clear", width=5, pady=1,
                                  command=lambda: self.wid_output.delete("1.0", "end"))
        wid_but_new = tk.Button(wid_frm, text="New window", pady=1,
                                command=lambda: create_dialog(self.tk, self.globals, False))
        wid_but_eval.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=1)
        wid_but_exec.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=1)
        wid_but_clear.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=1)
        wid_but_new.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=1)
        wid_frm.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        wid_tool_tip.tool_tip_add(wid_but_eval, "debug.eval")
        wid_tool_tip.tool_tip_add(wid_but_exec, "debug.exec")
        wid_tool_tip.tool_tip_add(wid_but_clear, "debug.clear")
        wid_tool_tip.tool_tip_add(wid_but_new, "debug.new")


    def __eval_input(self, use_exec):
        cmd = self.wid_input.get("1.0", "end")
        try:
            if use_exec:
                output = str(exec(cmd, self.globals))
            else:
                output = str(eval(cmd, self.globals))
        except Exception as e:
            output = str(e)

        self.wid_output.replace("1.0", "end", output)


    def __show_tagged_variable(self, xcoo, ycoo):
        txt = self.wid_output.get("@%d,%d linestart" % (xcoo, ycoo),
                                  "@%d,%d lineend" % (xcoo, ycoo))
        if txt:
            self.wid_var_name.delete(0, "end")
            self.wid_var_name.insert("end", txt)

            self.__show_variable_value(False)


    def __show_variable_value(self, auto_complete):
        var_ref = self.wid_var_name.get()

        if auto_complete:
            match = re.match(r"^(.*)\.(.*)$", var_ref)
            if match:
                try:
                    inst = eval(match.group(1), self.globals)
                    matches = [match.group(1) + "." + x for x in
                                inst.__dict__.keys() if x.startswith(match.group(2))]
                except:
                    matches = []
            else:
                matches = [x for x in self.globals if x.startswith(var_ref)]
        else:
            matches = [var_ref]

        if len(matches) == 1:
            try:
                val = eval(matches[0], self.globals)
            except:
                val = ""
            self.wid_input.replace("1.0", "end", "%s = %s" % (matches[0], val))
        else:
            self.wid_output.delete("1.0", "end")
            for var in matches:
                self.wid_output.insert("end", var, ["var_name"], "\n", [])

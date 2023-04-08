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
import gtest_gui.tool_tip_db as tool_tip_db


def enable_tips(enable):
    Tool_tip_widget.enable_tips = enable


def tool_tip_add(wid, key):
    if callable(key):
        msg = key
    else:
        msg = re.sub(r"\n", " ", tool_tip_db.tips[key].strip())

    wid.bind("<Leave>", lambda e: handle_leave())
    wid.bind("<Motion>", lambda e: handle_motion(wid, e.x, e.y, e.x_root, e.y_root, msg))


# ---- below is private ----


class Tool_tip_widget:
    enable_tips = True
    timer_id = None
    wid_anchor = None
    wid_tip = None
    cur_msg = ""
    under_construction = False


def handle_leave():
    if not Tool_tip_widget.under_construction:
        destroy_window()


def handle_motion(wid, wid_x, wid_y, wid_xroot, wid_yroot, msg):
    if not Tool_tip_widget.enable_tips:
        return

    if wid != Tool_tip_widget.wid_anchor:
        destroy_window()

    if Tool_tip_widget.wid_tip:
        if callable(msg):
            if msg(wid_x, wid_y) != Tool_tip_widget.cur_msg:
                destroy_window()
                handle_timer(wid, wid_x, wid_y, wid_xroot, wid_yroot, msg)

    else:
        if Tool_tip_widget.timer_id:
            tk_utils.tk_top.after_cancel(Tool_tip_widget.timer_id)
        Tool_tip_widget.timer_id = tk_utils.tk_top.after(
                                        1000, lambda: handle_timer(wid, wid_x, wid_y, wid_xroot, wid_yroot, msg))
        Tool_tip_widget.wid_anchor = wid


def handle_timer(wid, wid_x, wid_y, wid_xroot, wid_yroot, msg):
    Tool_tip_widget.timer_id = None
    Tool_tip_widget.wid_anchor = wid

    if callable(msg):
        msg = msg(wid_x, wid_y)
        if not msg:
            return
        Tool_tip_widget.cur_msg = msg

    destroy_window()
    create_window(msg)
    map_window(wid, wid_xroot, wid_yroot)


def create_window(msg):
    Tool_tip_widget.wid_tip = tk.Toplevel(tk_utils.tk_top)
    Tool_tip_widget.wid_tip.wm_overrideredirect(1)
    Tool_tip_widget.wid_tip.wm_withdraw()

    char_w = tk_utils.font_normal.measure("0")
    wid_lab = tk.Message(Tool_tip_widget.wid_tip, borderwidth=1, relief=tk.SUNKEN, bg="#FFFFA0",
                         text=msg, font=tk_utils.font_normal, anchor=tk.W, justify=tk.LEFT,
                         width=60*char_w)
    wid_lab.pack()

    wid_lab.bind("<Leave>", lambda e: handle_leave())


def map_window(wid, coord_x, coord_y):
    # Wait until the widget is constructed to allow querying its geometry
    Tool_tip_widget.under_construction = True
    Tool_tip_widget.wid_tip.update()

    # Window might have been destroyed while waiting
    if tk_utils.wid_exists(Tool_tip_widget.wid_tip):
        coord_x += 10
        coord_y -= 10 + Tool_tip_widget.wid_tip.winfo_reqheight()

        wid_w = Tool_tip_widget.wid_tip.winfo_reqwidth()
        root_w = Tool_tip_widget.wid_tip.winfo_screenwidth()
        if coord_x + wid_w > root_w:
            coord_x = root_w - wid_w
        if coord_x < 0:
            coord_x = 0

        wid_h = Tool_tip_widget.wid_tip.winfo_reqheight()
        root_h = Tool_tip_widget.wid_tip.winfo_screenheight()
        if coord_y + wid_h > root_h:
            coord_y = root_h - wid_h
        if coord_y < 0:
            coord_y = 0

        Tool_tip_widget.wid_tip.wm_geometry("+%d+%d" % (coord_x, coord_y))
        Tool_tip_widget.wid_tip.wm_deiconify()

    # Enable handler for leave event only after the widget is mapped 
    if Tool_tip_widget.wid_tip:
        Tool_tip_widget.wid_tip.update()
    Tool_tip_widget.under_construction = False


def destroy_window():
    if Tool_tip_widget.wid_tip:
        tk_utils.safe_destroy(Tool_tip_widget.wid_tip)

    if Tool_tip_widget.timer_id:
        tk_utils.tk_top.after_cancel(Tool_tip_widget.timer_id)

    Tool_tip_widget.timer_id = None
    Tool_tip_widget.wid_tip = None


# ---- Wrapper class ----

class Menu(tk.Menu):
    def __init__(self, parent, **kwargs):
        self.tooltip = {}
        super().__init__(parent, **kwargs)
        tool_tip_add(self, self.__get_tool_tip)


    def __get_tool_tip(self, xcoo, ycoo):
        idx = super().index("@" + str(ycoo))
        key = self.tooltip.get(idx, None)
        if key:
            if callable(key):
                return key()
            else:
                return re.sub(r"\n", " ", tool_tip_db.tips[key].strip())
        return ""


    def __install_tool_tip(self, kwargs, tooltip):
        if tooltip:
            idx = super().index(kwargs["label"])
            self.tooltip[idx] = tooltip


    def add_command(self, *cnf, **kwargs):
        tooltip = kwargs.pop("tooltip", None)
        super().add_command(*cnf, **kwargs)
        self.__install_tool_tip(kwargs, tooltip)


    def add_checkbutton(self, *cnf, **kwargs):
        tooltip = kwargs.pop("tooltip", None)
        super().add_checkbutton(*cnf, **kwargs)
        self.__install_tool_tip(kwargs, tooltip)


    def add_radiobutton(self, *cnf, **kwargs):
        tooltip = kwargs.pop("tooltip", None)
        super().add_radiobutton(*cnf, **kwargs)
        self.__install_tool_tip(kwargs, tooltip)

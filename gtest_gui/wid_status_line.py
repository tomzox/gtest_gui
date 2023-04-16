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

stline = None

def create_widget(tk_top, parent):
    global stline
    stline = Status_line_widget(tk_top, parent)


def show_message(msg_type, msg_txt):
    stline.show_message(msg_type, msg_txt)


def clear_message():
    stline.clear()


class Status_line_widget(object):
    def __init__(self, tk_top, parent):
        self.tk = tk_top
        self.wid_parent = parent
        self.timer_id = None
        self.wid_message = None
        self.msg_type = None
        self.fade_val = 0.0


    def show_message(self, msg_type, msg_txt):
        self.msg_type = msg_type
        self.fade_val = 0.0
        color = self.__get_color()

        if not tk_utils.wid_exists(self.wid_message):
            self.wid_message = tk.Label(self.wid_parent, text=msg_txt, foreground=color,
                                        anchor=tk.W, font=tk_utils.font_normal)

            self.wid_message.place(in_=self.wid_parent, anchor="se", bordermode="inside",
                                   x=(self.wid_parent.winfo_width() - 1),
                                   y=(self.wid_parent.winfo_height() - 1))

            self.wid_message.bind("<Motion>", lambda e: self.__handle_motion())

        else:
            self.wid_message.configure(text=msg_txt, foreground=color)

        if self.timer_id:
            self.tk.after_cancel(self.timer_id)
        self.timer_id = self.tk.after(5000, self.__handle_timer)


    def __get_color(self):
        if self.msg_type == "error":
            color = (0xff, 0, 0)
        elif self.msg_type == "warning":
            color = (0xff, 0xc0, 0)
        else:
            color = (0xff, 0xff, 0xff)

        factor = (1.0 - self.fade_val)
        color = [int(x * factor) for x in color]

        return "#%02X%02X%02X" % (color[0], color[1], color[2])


    def __handle_motion(self):
        self.msg_type = "motion"
        self.fade_val = 0
        self.wid_message.configure(foreground=self.__get_color())

        if self.timer_id:
            self.tk.after_cancel(self.timer_id)
        self.timer_id = self.tk.after(5000, self.__handle_timer)


    def __handle_timer(self):
        self.fade_val += 0.015
        if self.fade_val < 1:
            self.wid_message.config(foreground=self.__get_color())
            self.timer_id = self.tk.after(50, self.__handle_timer)

        else:
            self.timer_id = None
            self.clear()


    def clear(self):
        if self.timer_id:
            self.tk.after_cancel(self.timer_id)
            self.timer_id = None

        tk_utils.safe_destroy(self.wid_message)
        self.wid_message = None

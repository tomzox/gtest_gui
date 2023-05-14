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
This module implements the status line widget class.
"""

import tkinter as tk

import gtest_gui.tk_utils as tk_utils

class StatusLineWidget:
    """
    Status line widget class (singleton). Instances of this class exist
    temporarily while a status or warning message is to be displayed. The
    widget is placed as an overlay into the main window.
    """
    __stline = None

    @classmethod
    def create_widget(cls, tk_top, parent):
        """ Initializes the class."""
        cls.__stline = StatusLineWidget(tk_top, parent)


    @classmethod
    def get(cls):
        """ Returns the status line widget (singleton)."""
        return cls.__stline


    def __init__(self, tk_top, parent):
        self.tk_top = tk_top
        self.wid_parent = parent
        self.timer_id = None
        self.wid_message = None
        self.msg_type = None
        self.fade_val = 0.0


    def show_message(self, msg_type, msg_txt):
        """ Displays the overlay widget with the given text within the main window."""

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
            self.tk_top.after_cancel(self.timer_id)
        self.timer_id = self.tk_top.after(5000, self.__handle_timer)


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
            self.tk_top.after_cancel(self.timer_id)
        self.timer_id = self.tk_top.after(5000, self.__handle_timer)


    def __handle_timer(self):
        self.fade_val += 0.015
        if self.fade_val < 1:
            self.wid_message.config(foreground=self.__get_color())
            self.timer_id = self.tk_top.after(50, self.__handle_timer)

        else:
            self.timer_id = None
            self.clear_message()


    def clear_message(self):
        """ Clears the status message and hides the overlay widget."""
        if self.timer_id:
            self.tk_top.after_cancel(self.timer_id)
            self.timer_id = None

        tk_utils.safe_destroy(self.wid_message)
        self.wid_message = None

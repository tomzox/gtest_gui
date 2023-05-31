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
Implements the help dialog window class.
"""

import re
import tkinter as tk
import tkinter.font as tkf

import gtest_gui.tk_utils as tk_utils
import gtest_gui.config_db as config_db
import gtest_gui.help_db as help_db


class HelpDialog:
    """
    Help dialog window class (singleton): The dialog displays documentation
    text and a few basic command buttons for navigation.
    """
    __prev_dialog_wid = None

    __help_fg = "black"
    __help_bg = "#FFFFA0"
    __help_font_normal = None
    __help_font_fixed = None
    __help_font_bold = None
    __help_font_title1 = None
    __help_font_title2 = None


    @classmethod
    def create_dialog(cls, tk_top, index, subheading="", subrange=""):
        """
        Open the help dialog window. If an instance of the dialog already
        exists, the window is raised, else an instance is created.
        """
        if not cls.__help_font_normal:
            cls.__define_fonts()

        if cls.__prev_dialog_wid and tk_utils.wid_exists(cls.__prev_dialog_wid.wid_top):
            cls.__prev_dialog_wid.raise_window(index, subheading, subrange)
        else:
            cls.__prev_dialog_wid = HelpDialog(tk_top, index, subheading, subrange)


    @classmethod
    def __destroyed_dialog(cls):
        cls.__prev_dialog_wid = None


    @classmethod
    def __define_fonts(cls):
        cls.__help_font_fixed = "TkFixedFont"
        cls.__help_font_normal = tkf.Font(font="TkTextFont")

        opt = cls.__help_font_normal.configure()
        opt["weight"] = tkf.BOLD
        cls.__help_font_bold = tkf.Font(**opt)
        opt["size"] += 2
        cls.__help_font_title2 = tkf.Font(**opt)
        opt["size"] += 2
        cls.__help_font_title1 = tkf.Font(**opt)


    @staticmethod
    def add_menu_commands(tk_top, wid_men):
        """
        Adds a menu command for each help text chapter in the database to the
        given menu item. Each of the commands open the help dialog window if
        not yet open, then display the respective help text.
        """
        for idx in range(len(help_db.HELP_INDEX)):
            wid_men.add_command(label=help_db.HELP_INDEX[idx],
                                command=lambda idx=idx: HelpDialog.create_dialog(tk_top, idx))
            for sub in sorted([x[1] for x in help_db.HELP_SECTIONS if x[0] == idx]):
                title = help_db.HELP_SECTIONS[(idx, sub)]
                wid_men.add_command(label="- " + title,
                                    command=lambda idx=idx, title=title:
                                    HelpDialog.create_dialog(tk_top, idx, title))


    # -------------------------------------------------------------------------

    def __init__(self, tk_top, index, subheading, subrange):
        """ Create a Help dialog window and initially display the given chapter's text. """
        self.tk_top = tk_top
        self.chapter_idx = -1
        self.help_stack = []

        self.wid_top = tk.Toplevel(self.tk_top)
        self.wid_top.wm_title("GtestGui: Manual")
        self.wid_top.wm_group(self.tk_top)

        self.__create_buttons()
        self.__create_text_widget()

        if config_db.get_opt("help_win_geometry"):
            self.wid_top.wm_geometry(config_db.get_opt("help_win_geometry"))

        self.wid_top.bind("<Configure>", lambda e: self.__handle_window_resize(e.widget))
        self.wid_txt.focus_set()

        self.__fill_help_text(index, subheading, subrange)


    def __create_buttons(self):
        wid_frm = tk.Frame(self.wid_top)
        but_cmd_chpt = tk.Menubutton(wid_frm, text="Chapters", relief=tk.FLAT, underline=0)
        but_cmd_prev = tk.Button(wid_frm, text="Previous", width=7, relief=tk.FLAT, underline=0)
        but_cmd_next = tk.Button(wid_frm, text="Next", width=7, relief=tk.FLAT, underline=0)
        but_cmd_dismiss = tk.Button(wid_frm, text="Dismiss", relief=tk.FLAT,
                                    command=self.__destroy_window)
        but_cmd_chpt.grid(row=1, column=1, padx=5)
        but_cmd_prev.grid(row=1, column=3)
        but_cmd_next.grid(row=1, column=4)
        but_cmd_dismiss.grid(row=1, column=6, padx=5)
        wid_frm.columnconfigure(2, weight=1)
        wid_frm.columnconfigure(5, weight=1)
        wid_frm.pack(side=tk.TOP, fill=tk.X)
        wid_frm.bind("<Destroy>", lambda e: self.__destroy_window())

        men_chpt = tk.Menu(but_cmd_chpt, tearoff=0)
        but_cmd_chpt.configure(menu=men_chpt)
        HelpDialog.add_menu_commands(self.tk_top, men_chpt)

        self.but_cmd_prev = but_cmd_prev
        self.but_cmd_next = but_cmd_next

    def __create_text_widget(self):
        wid_frm = tk.Frame(self.wid_top)
        wid_txt = tk.Text(wid_frm, width=80, wrap=tk.WORD,
                          foreground=HelpDialog.__help_fg, background=HelpDialog.__help_bg,
                          font=HelpDialog.__help_font_normal,
                          spacing3=6, cursor="circle", takefocus=1)
        wid_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        wid_sb = tk.Scrollbar(wid_frm, orient=tk.VERTICAL, command=wid_txt.yview, takefocus=0)
        wid_txt.configure(yscrollcommand=wid_sb.set)
        wid_sb.pack(fill=tk.Y, anchor=tk.E, side=tk.LEFT)
        wid_frm.pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        # define tags for various nroff text formats
        wid_txt.tag_configure("title1", font=HelpDialog.__help_font_title1, spacing3=10)
        wid_txt.tag_configure("title2", font=HelpDialog.__help_font_title2,
                              spacing1=20, spacing3=10)
        wid_txt.tag_configure("indent", lmargin1=30, lmargin2=30)
        wid_txt.tag_configure("bold", font=HelpDialog.__help_font_bold)
        wid_txt.tag_configure("underlined", underline=1)
        wid_txt.tag_configure("fixed", font=HelpDialog.__help_font_fixed)
        wid_txt.tag_configure("pfixed", font=HelpDialog.__help_font_fixed,
                              spacing1=0, spacing2=0, spacing3=0)
        wid_txt.tag_configure("href", underline=1, foreground="blue")
        wid_txt.tag_bind("href", "<ButtonRelease-1>", lambda e: self.__follow_help_hyperlink())
        wid_txt.tag_bind("href", "<Enter>",
                         lambda e: self.wid_txt.configure(cursor="top_left_arrow"))
        wid_txt.tag_bind("href", "<Leave>", lambda e: self.wid_txt.configure(cursor="circle"))

        # allow to scroll the text with the cursor keys
        wid_txt.bindtags([wid_txt, "TextReadOnly", self.wid_top, "all"])
        wid_txt.bind("<Up>", lambda e, self=self: tk_utils.bind_call_and_break(
            lambda: wid_txt.yview(tk.SCROLL, -1, "unit")))
        wid_txt.bind("<Down>", lambda e, self=self: tk_utils.bind_call_and_break(
            lambda: wid_txt.yview(tk.SCROLL, 1, "unit")))
        wid_txt.bind("<Prior>", lambda e, self=self: tk_utils.bind_call_and_break(
            lambda: wid_txt.yview(tk.SCROLL, -1, "pages")))
        wid_txt.bind("<Next>", lambda e, self=self: tk_utils.bind_call_and_break(
            lambda: wid_txt.yview(tk.SCROLL, 1, "pages")))
        wid_txt.bind("<Home>", lambda e, self=self: tk_utils.bind_call_and_break(
            lambda: wid_txt.yview(tk.MOVETO, 0.0)))
        wid_txt.bind("<End>", lambda e, self=self: tk_utils.bind_call_and_break(
            lambda: wid_txt.yview(tk.MOVETO, 1.0)))
        wid_txt.bind("<Enter>", lambda e, self=self: tk_utils.bind_call_and_break(
            e.widget.focus_set))
        wid_txt.bind("<Escape>", lambda e: self.__destroy_window())
        wid_txt.bind("<Alt-Key-n>", lambda e: self.but_cmd_next.invoke())
        wid_txt.bind("<Alt-Key-p>", lambda e: self.but_cmd_prev.invoke())

        self.wid_txt = wid_txt


    def raise_window(self, index, subheading="", subrange=""):
        """ Raises the dialog window above all other windows."""
        self.wid_top.lift()
        self.__fill_help_text(index, subheading, subrange)


    def __fill_help_text(self, index, subheading, subrange):
        self.wid_txt.configure(state=tk.NORMAL)
        self.wid_txt.delete("1.0", "end")
        self.wid_txt.yview(tk.MOVETO, 0.0)

        # fill the widget with the formatted text
        for htext, tlabel in help_db.HELP_TEXTS[index]:
            self.wid_txt.insert("end", htext, tlabel)

        self.wid_txt.configure(state=tk.DISABLED)

        # bring the given text section into view
        if (len(subrange) == 2) and subrange[0]:
            self.wid_txt.see(subrange[1])
            self.wid_txt.see(subrange[0])
        elif subheading:
            # search for the string at the beginning of the line only
            # (prevents matches on hyperlinks)
            pattern = "^" + str(subheading)
            pos = self.wid_txt.search(pattern, regexp=True, index="1.0")
            if pos:
                self.wid_txt.see(pos)
                # make sure the header is at the top of the page
                bbox = self.wid_txt.bbox(pos)
                if bbox:
                    bbox_y = bbox[1]
                    bbox_h = bbox[3]
                    self.wid_txt.yview(tk.SCROLL, bbox_y // bbox_h, "units")
                    self.wid_txt.see(pos)

        # define/update bindings for left/right command buttons
        if index > 0:
            self.but_cmd_prev.configure(command=lambda:
                                        self.raise_window(index - 1), state=tk.NORMAL)
        else:
            self.but_cmd_prev.configure(command=lambda: None, state=tk.DISABLED)

        if index + 1 < len(help_db.HELP_TEXTS):
            self.but_cmd_next.configure(command=lambda:
                                        self.raise_window(index + 1), state=tk.NORMAL)
        else:
            self.but_cmd_next.configure(command=lambda: None, state=tk.DISABLED)

        self.chapter_idx = index


    def __destroy_window(self):
        tk_utils.safe_destroy(self.wid_top)
        HelpDialog.__destroyed_dialog()


    def __follow_help_hyperlink(self):
        # the text under the mouse carries the mark 'current'
        curidx = self.wid_txt.index("current + 1 char")

        # determine the range of the 'href' tag under the mouse
        href_range = self.wid_txt.tag_prevrange("href", curidx)

        # cut out the text in that range
        hlink = self.wid_txt.get(*href_range)

        # check if the text contains a sub-section specification
        match = re.match(r"(.*): *(.*)", hlink)
        if match:
            hlink = match.group(1)
            subsect = match.group(2)
        else:
            subsect = ""

        try:
            idx = help_db.HELP_INDEX.index(hlink)
            self.raise_window(idx, subsect)
        except ValueError:
            pass


    # callback for Configure (aka resize) event on the toplevel window
    def __handle_window_resize(self, wid):
        if wid == self.wid_top:
            new_size = self.wid_top.wm_geometry()
            config_db.set_opt("help_win_geometry", new_size)

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
Implements the job list dialog window class.
"""

import tkinter as tk
from tkinter import messagebox as tk_messagebox

import gtest_gui.config_db as config_db
import gtest_gui.dlg_browser as dlg_browser
import gtest_gui.gtest_ctrl as gtest_ctrl
import gtest_gui.test_db as test_db
import gtest_gui.tk_utils as tk_utils
from gtest_gui.wid_text_sel import TextSelWidget


class JobListDialog:
    """
    This class implements a job list dialog window as a singleton. Instances of the class are
    created via class function create_dialog(), which only creates a new instance if none exists
    yet. The dialog window shows a list of all test processes started by the current test campaign.
    For each process statistics about received trace and yet pending results are shown. Processes
    can be aborted via a context menu.
    """
    __prev_dialog_wid = None

    @classmethod
    def create_dialog(cls, tk_top):
        """
        Open the configuration dialog window. If an instance of the dialog
        already exists, the window is raised, else an instance is created.
        """
        if not test_db.test_case_names:
            msg = "Test case list is empty, no tests can run."
            tk_messagebox.showerror(parent=tk_top, message=msg)
            return

        if cls.__prev_dialog_wid and tk_utils.wid_exists(cls.__prev_dialog_wid.wid_top):
            cls.__prev_dialog_wid.raise_window()
        else:
            cls.__prev_dialog_wid = JobListDialog(tk_top)


    @classmethod
    def __destroyed_dialog(cls):
        cls.__prev_dialog_wid = None


    def __init__(self, tk_top):
        self.tk_top = tk_top
        self.table_header_txt = ("PID", "BgJob", "Traced", "#Results", "Done", "Current test case")

        self.__create_dialog_window()
        self.__populate_table()
        self.timer_id = self.tk_top.after(500, self.__update_by_timer)


    def __destroy_window(self):
        tk_utils.safe_destroy(self.wid_top)
        self.tk_top.after_cancel(self.timer_id)
        JobListDialog.__destroyed_dialog()


    def raise_window(self):
        """ Raises the dialog window above all other windows."""
        self.wid_top.wm_deiconify()
        self.wid_top.lift()


    def __create_dialog_window(self):
        self.wid_top = tk.Toplevel(self.tk_top)
        self.wid_top.wm_title("GtestGui: Test job list")
        self.wid_top.wm_group(self.tk_top)

        self.wid_table, self.wid_header = self.__create_table_widget()

        self.wid_top.bind("<ButtonRelease-3>", lambda e: self.__post_context_menu(e.widget,
                                                                                  e.x, e.y))
        self.wid_top.bind("<Configure>", lambda e: self.__handle_window_resize(e.widget))
        self.wid_top.bind("<Destroy>", lambda e: self.__destroy_window())

        self.wid_header.tag_configure("head", font=tk_utils.font_content_bold, lmargin1=5)
        self.wid_table.tag_configure("body", lmargin1=5)
        self.wid_table.tag_configure("bold", font=tk_utils.font_content_bold)

        self.wid_header.insert("0.0", "\t".join(self.table_header_txt), "head", "\n", [])
        self.__update_column_widths()

        self.sel_obj = TextSelWidget(self.wid_table, self.__handle_selection_change, self.__get_len)

        if config_db.get_opt("job_list_geometry"):
            self.wid_top.wm_geometry(config_db.get_opt("job_list_geometry"))

        self.wid_table.focus_set()


    def __create_table_widget(self):
        initial_height = 10

        wid_frm1 = tk.Frame(self.wid_top)
        wid_frm2 = tk.Frame(wid_frm1, relief=tk.SUNKEN, borderwidth=2)
        wid_header = tk.Text(wid_frm2, height=1, font=tk_utils.font_content,
                             insertofftime=0, wrap=tk.NONE, cursor="top_left_arrow",
                             exportselection=0, relief=tk.FLAT, takefocus=0)
        wid_table = tk.Text(wid_frm2, height=initial_height, font=tk_utils.font_content,
                            insertofftime=0, wrap=tk.NONE, cursor="top_left_arrow",
                            exportselection=0, relief=tk.FLAT)
        wid_header.pack(side=tk.TOP, fill=tk.X)
        wid_table.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        wid_frm2.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

        wid_sb = tk.Scrollbar(wid_frm1, orient=tk.VERTICAL, command=wid_table.yview, takefocus=0)
        wid_table.configure(yscrollcommand=wid_sb.set)
        wid_sb.pack(side=tk.LEFT, fill=tk.Y)
        wid_frm1.pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        wid_header.bindtags([wid_header, self.wid_top, "all"])
        wid_table.bindtags([wid_table, self.wid_top, "TextSel", "all"])

        return (wid_table, wid_header)


    def __update_column_widths(self):
        char_w = tk_utils.font_content.measure("0")
        if char_w == 0:
            char_w = 15

        title_text = self.table_header_txt
        tab_widths = [tk_utils.font_content_bold.measure(x) + 2*char_w for x in title_text]

        max_width = tk_utils.font_content.measure("9999999") + 2*char_w
        if max_width > tab_widths[0]:
            tab_widths[0] = max_width

        max_width = tk_utils.font_content.measure("99999999") + 2*char_w
        if max_width > tab_widths[2]:
            tab_widths[2] = max_width

        max_width = tk_utils.font_content.measure("100%") + 2*char_w
        if max_width > tab_widths[4]:
            tab_widths[4] = max_width

        max_width = max([tk_utils.font_content.measure(x)
                         for x in test_db.test_case_names]) + 2*char_w
        if max_width > tab_widths[5]:
            tab_widths[5] = max_width

        off = char_w + tab_widths[0]
        tabs = []
        for width in tab_widths[1:5]:
            tabs.extend([off + width/2, "center"])
            off += width
        tabs.extend([off + char_w, "left"])

        self.wid_header.tag_configure("head", font=tk_utils.font_content_bold, tabs=tabs,
                                      lmargin1=5)
        self.wid_table.tag_configure("body", tabs=tabs, lmargin1=5)

        # Convert pixel width to a character count (assuming "0" has average char width)
        nof_chars = (sum(tab_widths) + char_w * 3 - 1) // char_w

        self.wid_header.configure(width=nof_chars)
        self.wid_table.configure(width=nof_chars)


    def __handle_window_resize(self, wid):
        if wid == self.wid_top:
            new_size = self.wid_top.wm_geometry()
            config_db.set_opt("job_list_geometry", new_size)


    @staticmethod
    def __format_table_row(stats):
        perc_done = (100 * stats[4]) // stats[5] if stats[5] else 100
        is_bg_job = "yes" if stats[2] else "no"
        msg = ("%d\t%s\t%d\t%d\t%d%%\t%s\n" %
               (stats[0], is_bg_job, stats[3], stats[4], perc_done, stats[6]))
        return [msg, "body"]


    def __populate_table(self):
        self.sel_obj.text_sel_set_selection([])
        self.wid_table.delete("1.0", "end")

        self.job_stats = gtest_ctrl.gtest_ctrl.get_job_stats()
        if self.job_stats:
            for stat in self.job_stats:
                msg = JobListDialog.__format_table_row(stat)
                self.wid_table.insert("end", *msg)
        else:
            self.wid_table.insert("end", "\nCurrently, no jobs are running\n")


    def __update_by_timer(self):
        sel_pids = [self.job_stats[x][0] for x in self.sel_obj.text_sel_get_selection()]

        self.__populate_table()

        new_pids = [x[0] for x in self.job_stats]
        new_sel = []
        for pid in sel_pids:
            try:
                new_sel.append(new_pids.index(pid))
            except ValueError:
                pass
        self.sel_obj.text_sel_set_selection(new_sel)

        self.timer_id = self.tk_top.after(500, self.__update_by_timer)


    def __handle_selection_change(self, sel):
        # abstract interface: unused parameter needed by other classes
        # pylint: disable=unused-argument
        self.sel_obj.text_sel_copy_clipboard(False)


    def __get_len(self):
        return len(self.job_stats)


    def __post_context_menu(self, parent, xcoo, ycoo):
        wid_men = tk_utils.get_context_menu_widget()

        if (parent == self.wid_table) and gtest_ctrl.gtest_ctrl.is_active():
            self.sel_obj.text_sel_context_selection(xcoo, ycoo)
            sel = self.sel_obj.text_sel_get_selection()
            if sel:
                if len(sel) == 1:
                    wid_men.add_command(label="Open trace output file",
                                        command=lambda file_name=self.job_stats[sel[0]][1]:
                                        JobListDialog.__do_open_trace(file_name))
                    wid_men.add_separator()

                wid_men.add_command(label="Send ABORT signal to selected processes",
                                    command=lambda pids=[self.job_stats[x][0] for x in sel]:
                                    JobListDialog.__do_abort_jobs(pids))

                tk_utils.post_context_menu(parent, xcoo, ycoo)


    @staticmethod
    def __do_abort_jobs(pids):
        for pid in pids:
            gtest_ctrl.gtest_ctrl.abort_job(pid)


    @staticmethod
    def __do_open_trace(trace_file_name):
        dlg_browser.show_trace(trace_file_name)

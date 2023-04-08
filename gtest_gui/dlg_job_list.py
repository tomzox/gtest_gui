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
# This class implements the test case list dialog.
#

import tkinter as tk
from tkinter import messagebox as tk_messagebox

import gtest_gui.config_db as config_db
import gtest_gui.dlg_browser as dlg_browser
import gtest_gui.filter_expr as filter_expr
import gtest_gui.gtest as gtest
import gtest_gui.test_db as test_db
import gtest_gui.tk_utils as tk_utils
import gtest_gui.wid_test_ctrl as wid_test_ctrl
import gtest_gui.wid_text_sel as wid_text_sel


prev_dialog_wid = None
prev_export_filename = ""


def create_dialog(tk_top):
    global prev_dialog_wid

    if not test_db.test_case_names:
        tk_messagebox.showerror(parent=tk_top, message="Test case list is empty, no tests can run.")
        return

    if prev_dialog_wid and tk_utils.wid_exists(prev_dialog_wid.wid_top):
        prev_dialog_wid.raise_window()
    else:
        prev_dialog_wid = Job_list_dialog(tk_top)


class Job_list_dialog(object):
    def __init__(self, tk_top):
        self.tk = tk_top
        self.table_header_txt = ("PID", "Traced", "#Results", "Current test case")

        self.__create_dialog_window()
        self.__populate_table()
        self.timer_id = self.tk.after(500, self.__update_by_timer)


    def __destroy_window(self):
        global prev_dialog_wid
        tk_utils.safe_destroy(self.wid_top)
        self.tk.after_cancel(self.timer_id)
        prev_dialog_wid = None


    def raise_window(self):
        self.wid_top.wm_deiconify()
        self.wid_top.lift()


    def __create_dialog_window(self):
        self.wid_top = tk.Toplevel(self.tk)
        self.wid_top.wm_title("GtestGui: Test job list")
        self.wid_top.wm_group(self.tk)

        self.__create_table_widget()

        self.wid_top.bind("<ButtonRelease-3>", lambda e: self.__post_context_menu(e.widget,
                                                                                  e.x, e.y))
        self.wid_top.bind("<Configure>", lambda e: self.__handle_window_resize(e.widget))
        self.wid_top.bind("<Destroy>", lambda e: self.__destroy_window())

        self.wid_header.tag_configure("head", font=tk_utils.font_content_bold,
                                      spacing1=2, spacing3=5, lmargin1=5)
        self.wid_table.tag_configure("body", lmargin1=5)
        self.wid_table.tag_configure("bold", font=tk_utils.font_content_bold)

        self.wid_header.insert("0.0", "\t".join(self.table_header_txt), "head", "\n", [])
        self.__update_column_widths()

        self.sel_obj = wid_text_sel.Text_sel_wid(self.wid_table,
                                                 self.__handle_selection_change, self.__get_len)

        if config_db.job_list_geometry:
            self.wid_top.wm_geometry(config_db.job_list_geometry)

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

        self.wid_table = wid_table
        self.wid_header = wid_header


    def __update_column_widths(self):
        char_w = tk_utils.font_content.measure("0")
        if char_w == 0: char_w = 15

        title_text = self.table_header_txt
        tab_widths = [tk_utils.font_content_bold.measure(x) + 2*char_w for x in title_text]

        max_width = tk_utils.font_content.measure("9999999") + 2*char_w
        if max_width > tab_widths[0]:
            tab_widths[0] = max_width

        max_width = tk_utils.font_content.measure("99999999") + 2*char_w
        if max_width > tab_widths[1]:
            tab_widths[1] = max_width

        max_width = max([tk_utils.font_content.measure(x)
                            for x in test_db.test_case_names]) + 2*char_w
        if max_width > tab_widths[3]:
            tab_widths[3] = max_width

        off = char_w + tab_widths[0]
        tabs = [off + tab_widths[1]/2, "center",
                off + tab_widths[1] + tab_widths[2]/2, "center",
                off + tab_widths[1] + tab_widths[2] + char_w, "left"]

        self.wid_header.tag_configure("head", font=tk_utils.font_content_bold, tabs=tabs,
                                      spacing1=2, spacing3=5, lmargin1=5)
        self.wid_table.tag_configure("body", tabs=tabs, lmargin1=5)

        # Convert pixel width to a character count (assuming "0" has average char width)
        nof_chars = (sum(tab_widths) + char_w * 3 - 1) // char_w

        self.wid_header.configure(width=nof_chars)
        self.wid_table.configure(width=nof_chars)


    def __handle_window_resize(self, wid):
        if wid == self.wid_top:
            new_size = self.wid_top.wm_geometry()
            if new_size != config_db.job_list_geometry:
                config_db.job_list_geometry = new_size
                config_db.rc_file_update_after_idle()


    def __format_table_row(self, stats):
        msg = "%d\t%d\t%d\t%s\n" % (stats[0], stats[2], stats[3], stats[4])
        return [msg, "body"]


    def __populate_table(self):
        self.sel_obj.text_sel_set_selection([])
        self.wid_table.delete("1.0", "end")

        self.job_stats = gtest.gtest_ctrl.get_job_stats()
        if self.job_stats:
            for idx in range(len(self.job_stats)):
                msg = self.__format_table_row(self.job_stats[idx])
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

        self.timer_id = self.tk.after(500, self.__update_by_timer)


    def __handle_selection_change(self, sel):
        self.sel_obj.text_sel_copy_clipboard(False)


    def __get_len(self):
        return len(self.job_stats)


    def __post_context_menu(self, parent, xcoo, ycoo):
        wid_men = tk_utils.get_context_menu_widget()

        if (parent == self.wid_table) and gtest.gtest_ctrl.is_active():
            self.sel_obj.text_sel_context_selection(xcoo, ycoo)
            sel = self.sel_obj.text_sel_get_selection()
            if sel:
                if len(sel) == 1:
                    wid_men.add_command(label="Open trace output file",
                                        command=lambda file_name=self.job_stats[sel[0]][1]:
                                            self.__do_open_trace(file_name))
                    wid_men.add_separator()

                wid_men.add_command(label="Send ABORT signal to selected processes",
                                    command=lambda pids=[self.job_stats[x][0] for x in sel]:
                                            self.__do_abort_jobs(pids))

                tk_utils.post_context_menu(parent, xcoo, ycoo)


    def __do_abort_jobs(self, pids):
        for pid in pids:
          gtest.gtest_ctrl.abort_job(pid)


    def __do_open_trace(self, trace_file_name):
        dlg_browser.show_trace(self.tk, trace_file_name)

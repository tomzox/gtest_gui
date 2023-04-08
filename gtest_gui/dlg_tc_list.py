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

from enum import Enum
import os
import tkinter as tk
from tkinter import messagebox as tk_messagebox
from tkinter import filedialog as tk_filedialog

import gtest_gui.bisect as bisect
import gtest_gui.config_db as config_db
import gtest_gui.filter_expr as filter_expr
import gtest_gui.gtest as gtest
import gtest_gui.test_db as test_db
import gtest_gui.tk_utils as tk_utils
import gtest_gui.wid_test_ctrl as wid_test_ctrl
import gtest_gui.wid_text_sel as wid_text_sel


prev_dialog_wid = None
prev_export_filename = ""

class Sort_mode(Enum):
    by_name = 0
    by_exec_cnt = 1
    by_fail_cnt = 2
    by_duration = 3


def create_dialog(tk_top, test_ctrl):
    global prev_dialog_wid

    if not test_db.test_case_names:
        tk_messagebox.showerror(parent=tk_top, message="Test case list is empty.")
        return

    if not test_ctrl.check_filter_expression():
        return

    if prev_dialog_wid and tk_utils.wid_exists(prev_dialog_wid.wid_top):
        prev_dialog_wid.raise_window()
    else:
        prev_dialog_wid = Tc_list_dialog(tk_top, test_ctrl)


class Tc_list_dialog(object):
    def __init__(self, tk_top, test_ctrl):
        self.tk = tk_top
        self.test_ctrl = test_ctrl
        self.table_header_txt = ("Run", "Name", "Passed", "Failed", "Exec time")
        self.opt_sort_modes = []

        self.__create_dialog_window()
        self.__handle_filter_change()

        test_db.Test_db_slots.tc_stats_update = self.__handle_tc_stats_update
        test_db.Test_db_slots.tc_names_update = self.__handle_tc_names_update
        test_db.Test_db_slots.campaign_stats_reset = self.__handle_campaign_status_change
        self.test_ctrl.register_filter_change_slot(self.__handle_main_tc_filter_expr_change)


    def __destroy_window(self):
        global prev_dialog_wid
        test_db.Test_db_slots.tc_stats_update = None
        test_db.Test_db_slots.tc_names_update = None
        test_db.Test_db_slots.campaign_stats_reset = None

        self.test_ctrl.register_filter_change_slot(None)

        tk_utils.safe_destroy(self.wid_top)
        prev_dialog_wid = None


    def raise_window(self):
        self.wid_top.wm_deiconify()
        self.wid_top.lift()


    def __create_dialog_window(self):
        self.wid_top = tk.Toplevel(self.tk)
        self.wid_top.wm_title("GtestGui: Test case list")
        self.wid_top.wm_group(self.tk)

        self.var_filter_run = tk.BooleanVar(self.tk, False)
        self.var_filter_failed = tk.BooleanVar(self.tk, False)
        self.var_filter_disabled = tk.BooleanVar(self.tk, False)

        self.var_sort_name = tk.BooleanVar(self.tk, False)
        self.var_sort_exec_cnt = tk.BooleanVar(self.tk, False)
        self.var_sort_fail_cnt = tk.BooleanVar(self.tk, False)
        self.var_sort_duration = tk.BooleanVar(self.tk, False)

        self.__create_table_widget()

        self.wid_table.bind("<Key-Return>", lambda e: self.__do_filter_selected_tests(True))
        self.wid_table.bind("<Key-Delete>", lambda e: self.__do_filter_selected_tests(False))
        self.wid_table.bind("<FocusIn>", lambda e: self.test_ctrl.check_filter_expression(False))

        self.wid_top.bind("<ButtonRelease-3>", lambda e: self.__post_context_menu(e.widget, e.x, e.y))
        self.wid_top.bind("<Configure>", lambda e: self.__handle_window_resize(e.widget))
        self.wid_top.bind("<Destroy>", lambda e: self.__destroy_window())

        self.wid_header.tag_configure("head", font=tk_utils.font_content_bold,
                                      lmargin1=5, spacing1=2, spacing3=5)
        self.wid_table.tag_configure("body", lmargin1=5)
        self.wid_table.tag_configure("bold", font=tk_utils.font_content_bold)

        self.wid_header.insert("0.0", "\t".join(self.table_header_txt), "head", "\n", [])
        self.__update_column_widths()

        self.sel_obj = wid_text_sel.Text_sel_wid(self.wid_table,
                                                 self.__handle_selection_change, self.__get_len)

        if config_db.tc_list_geometry:
            self.wid_top.wm_geometry(config_db.tc_list_geometry)

        self.wid_table.focus_set()


    def __create_table_widget(self):
        initial_height = min(40, len(test_db.test_case_names) + 1)

        wid_frm1 = tk.Frame(self.wid_top)
        wid_frm2 = tk.Frame(wid_frm1, borderwidth=2, relief=tk.SUNKEN)
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

        tc_max_width = max([tk_utils.font_content.measure(x)
                                for x in test_db.test_case_names]) + 2*char_w
        if tc_max_width > tab_widths[1]:
            tab_widths[1] = tc_max_width

        tabs = [char_w + tab_widths[0], "left"]
        off = tab_widths[0] + tab_widths[1]
        for width in tab_widths[2:]:
            tabs.extend([off + width/2, "center"])
            off += width

        self.wid_header.tag_configure("head", font=tk_utils.font_content_bold, tabs=tabs,
                                      lmargin1=5, spacing1=2, spacing3=5)
        self.wid_table.tag_configure("body", tabs=tabs, lmargin1=5)

        # Convert pixel width to a character count (assuming "0" has average char width)
        nof_chars = (off + char_w - 1) // char_w

        self.wid_header.configure(width=nof_chars)
        self.wid_table.configure(width=nof_chars)


    def __handle_window_resize(self, wid):
        if wid == self.wid_top:
            new_size = self.wid_top.wm_geometry()
            if new_size != config_db.tc_list_geometry:
                config_db.tc_list_geometry = new_size
                config_db.rc_file_update_after_idle()


    def __format_table_row(self, tc_name):
        tc_stats = test_db.test_case_stats[tc_name]
        txt = []

        ena = "yes\t" if tc_name in self.tc_enabled else "no\t"
        txt.extend([ena + tc_name, "body"])

        nof_pass = tc_stats[0]
        if nof_pass > 0:
            txt.extend(["\t%d" % nof_pass, ["body", "bold"]])
        else:
            txt.extend(["\t%d" % nof_pass, "body"])

        nof_fail = tc_stats[1]
        if nof_fail > 0:
            txt.extend(["\t%d" % nof_fail, ["body", "bold"]])
        else:
            txt.extend(["\t%d" % nof_fail, "body"])

        duration = tc_stats[3] / 1000 # FP result
        if duration < 10:
            duration = "\t%.3f" % duration
        elif duration < 3600:
            duration = "\t%02d:%02d" % (duration/60, duration%60)
        else:
            duration = "\t%d:%02d:%02d" % (duration/3600, (duration/60)%60, duration%60)
        txt.extend([duration + "\n", "body"])

        return txt


    def __handle_tc_stats_update(self, tc_name):
        try:
            line_idx = self.tc_list_sorted.index(tc_name)
        except ValueError:
            line_idx = None

        if line_idx is None:
            if self.__matches_filter(tc_name):
                line_idx = bisect.bisect_left(self.tc_list_sorted, tc_name,
                                              self.__get_sort_key_fn())
                self.__insert_single(tc_name, line_idx)
        else:
            if self.__matches_filter(tc_name):
                if self.__check_sort_order(tc_name, line_idx):
                    self.__replace_single(tc_name, line_idx)
                else:
                    self.__delete_single(tc_name, line_idx)
                    line_idx = bisect.bisect_left(self.tc_list_sorted, tc_name,
                                                  self.__get_sort_key_fn())
                    self.__insert_single(tc_name, line_idx)
            else:
                self.__delete_single(tc_name, line_idx)


    def __replace_single(self, tc_name, line_idx):
        txt = self.__format_table_row(tc_name)
        self.wid_table.replace("%d.0" % (line_idx + 1), "%d.0" % (line_idx + 2), *txt)
        self.sel_obj.text_sel_show_selection()


    def __insert_single(self, tc_name, line_idx):
        txt = self.__format_table_row(tc_name)
        self.wid_table.insert("%d.0" % (line_idx + 1), *txt)

        self.tc_list_sorted.insert(line_idx, tc_name)
        self.sel_obj.text_sel_adjust_insert(line_idx)


    def __delete_single(self, tc_name, line_idx):
        line_1 = "%d.0" % (line_idx + 1)
        line_2 = "%d.0" % (line_idx + 2)
        self.wid_table.delete(line_1, line_2)

        del self.tc_list_sorted[line_idx]
        self.sel_obj.text_sel_adjust_deletion(line_idx)


    def __populate_table(self):
        self.wid_table.delete("1.0", "end")
        for tc_name in self.tc_list_sorted:
            txt = self.__format_table_row(tc_name)
            self.wid_table.insert("end", *txt)

        self.sel_obj.text_sel_set_selection([])


    def __refill_table(self):
        prev_yview = self.wid_table.yview()[0]
        prev_sel = self.sel_obj.text_sel_get_selection()

        self.__populate_table()

        self.wid_table.yview_moveto(prev_yview)
        self.sel_obj.text_sel_set_selection(prev_sel)


    def __handle_campaign_status_change(self):
        for tc_name in test_db.test_case_names:
            self.__handle_tc_stats_update(tc_name)


    def __handle_main_tc_filter_expr_change(self, expr):
        self.tc_enabled = expr.get_selected_tests()

        if self.var_filter_run.get():
            self.__handle_filter_change()
        else:
            self.__refill_table()


    def __handle_tc_names_update(self):
        self.__update_column_widths()
        self.__handle_filter_change()


    def __handle_filter_change(self):
        self.tc_enabled = self.test_ctrl.get_test_filter_expr().get_selected_tests()

        filter_run = self.var_filter_run.get()
        filter_failed = self.var_filter_failed.get()
        filter_disabled = self.var_filter_disabled.get()
        tc_list = []

        for tc_name in test_db.test_case_names:
            if self.__matches_filter(tc_name):
                tc_list.append(tc_name)

        self.tc_list_sorted = self.__sort_tc_list(tc_list)
        self.__populate_table()


    def __matches_filter(self, tc_name):
        tc_stats = test_db.test_case_stats[tc_name]
        return ( (not self.var_filter_run.get() or tc_name in self.tc_enabled) and
                 (not self.var_filter_failed.get() or tc_stats[1]) and
                 (not self.var_filter_disabled.get() or not filter_expr.is_disabled_by_name(tc_name)) )


    def __get_sort_key_fn(self):
        if self.opt_sort_modes:
            return lambda x: Tc_list_dialog.__get_sort_keys(self.opt_sort_modes, x)
        else:
            return lambda x: x


    @staticmethod
    def __get_sort_keys(opt_sort_modes, tc_name):
        keys = []
        for mode in opt_sort_modes:
            if mode == Sort_mode.by_name:
                keys.append(tc_name)

            elif mode == Sort_mode.by_exec_cnt:
                keys.append(0 - test_db.test_case_stats[tc_name][0]
                              - test_db.test_case_stats[tc_name][1]
                              - test_db.test_case_stats[tc_name][2])

            elif mode == Sort_mode.by_fail_cnt:
                keys.append(0 - test_db.test_case_stats[tc_name][1])

            elif mode == Sort_mode.by_duration:
                keys.append(0 - test_db.test_case_stats[tc_name][3])
        return keys


    def __sort_tc_list(self, tc_list):
        for mode in reversed(self.opt_sort_modes):
            if mode == Sort_mode.by_name:
                tc_list = sorted(tc_list)
            elif mode == Sort_mode.by_exec_cnt:
                tc_list = sorted(tc_list, key=lambda x: 0 - test_db.test_case_stats[x][0]
                                                          - test_db.test_case_stats[x][1]
                                                          - test_db.test_case_stats[x][2])
            elif mode == Sort_mode.by_fail_cnt:
                tc_list = sorted(tc_list, key=lambda x: 0 - test_db.test_case_stats[x][1])
            elif mode == Sort_mode.by_duration:
                tc_list = sorted(tc_list, key=lambda x: 0 - test_db.test_case_stats[x][3])
        return tc_list


    def __check_sort_order(self, tc_name, line_idx):
        if self.opt_sort_modes:
            if line_idx > 0:
                prev_name = self.tc_list_sorted[line_idx - 1]
                if (Tc_list_dialog.__get_sort_keys(self.opt_sort_modes, tc_name)
                        < Tc_list_dialog.__get_sort_keys(self.opt_sort_modes, prev_name)):
                    return False

            if line_idx + 1 < len(self.tc_list_sorted):
                next_name = self.tc_list_sorted[line_idx + 1]
                if (Tc_list_dialog.__get_sort_keys(self.opt_sort_modes, next_name)
                        < Tc_list_dialog.__get_sort_keys(self.opt_sort_modes, tc_name)):
                    return False

        return True


    def __get_len(self):
        return len(self.tc_list_sorted)


    def __handle_selection_change(self, sel):
        self.sel_obj.text_sel_copy_clipboard(False)


    def __get_mapped_selection(self):
        sel = self.sel_obj.text_sel_get_selection()
        return [self.tc_list_sorted[x] for x in sel]


    def __post_context_menu(self, parent, xcoo, ycoo):
        wid_men = tk_utils.get_context_menu_widget()

        if (parent == self.wid_table) and not gtest.gtest_ctrl.is_active():
            self.sel_obj.text_sel_context_selection(xcoo, ycoo)
            expr = self.test_ctrl.get_test_filter_expr()

            sel = self.__get_mapped_selection()
            if not expr.run_disabled():
                sel = [x for x in sel if not filter_expr.is_disabled_by_name(x)]

            if sel:
                plural_s = "" if len(sel) == 1 else "s"
                need_sep = False

                if any([expr.can_select_test(x) for x in sel]):
                    wid_men.add_command(label="Add selected test case%s to filter" % plural_s,
                                        command=lambda: self.test_ctrl.select_tcs(sel, True))
                    need_sep = True
                if any([expr.can_deselect_test(x) for x in sel]):
                    wid_men.add_command(label="Remove selected test case%s from filter" % plural_s,
                                        command=lambda: self.test_ctrl.select_tcs(sel, False))
                    need_sep = True

                all_tc_names = filter_expr.get_test_list(expr.run_disabled())
                tc_names = []
                for tc_suite in filter_expr.get_test_suite_names(sel):
                    tc_names.extend(filter_expr.get_tests_in_test_suite(tc_suite, all_tc_names))

                if any([expr.can_select_test(x) for x in tc_names]):
                    wid_men.add_command(label="Add selected test suites to filter",
                                        command=lambda: self.test_ctrl.select_tcs(tc_names, True))
                    need_sep = True
                if any([expr.can_deselect_test(x) for x in tc_names]):
                    wid_men.add_command(label="Remove selected test suites from filter",
                                        command=lambda: self.test_ctrl.select_tcs(tc_names, False))
                    need_sep = True

                if need_sep:
                    wid_men.add_separator()

        wid_men.add_checkbutton(label="Show only tests enabled to run",
                                 command=self.__handle_filter_change, variable=self.var_filter_run)
        wid_men.add_checkbutton(label="Show only failed tests",
                                 command=self.__handle_filter_change, variable=self.var_filter_failed)
        wid_men.add_checkbutton(label="Show no DISABLED tests",
                                 command=self.__handle_filter_change, variable=self.var_filter_disabled)
        wid_men.add_separator()

        wid_men.add_checkbutton(
                label="Sort by test case name",
                command=lambda: self.__do_toggle_sort_mode(self.var_sort_name.get(), Sort_mode.by_name),
                variable=self.var_sort_name)
        wid_men.add_checkbutton(
                label="Sort by execution count",
                command=lambda: self.__do_toggle_sort_mode(self.var_sort_exec_cnt.get(), Sort_mode.by_exec_cnt),
                variable=self.var_sort_exec_cnt)
        wid_men.add_checkbutton(
                label="Sort by failure count",
                command=lambda: self.__do_toggle_sort_mode(self.var_sort_fail_cnt.get(), Sort_mode.by_fail_cnt),
                variable=self.var_sort_fail_cnt)
        wid_men.add_checkbutton(
                label="Sort by duration",
                command=lambda: self.__do_toggle_sort_mode(self.var_sort_duration.get(), Sort_mode.by_duration),
                variable=self.var_sort_duration)
        wid_men.add_separator()

        wid_men.add_command(label="Export list to file...", command=self.__do_export_pass_fail)
        wid_men.add_command(label="Close window", command=self.__destroy_window)

        tk_utils.post_context_menu(parent, xcoo, ycoo)


    def __do_export_pass_fail(self):
        global prev_export_filename
        filename = tk_filedialog.asksaveasfilename(
                        parent=self.wid_top,
                        filetypes=[("all", "*"), ("Text", "*.txt")],
                        title="Select output file",
                        initialfile=os.path.basename(prev_export_filename),
                        initialdir=os.path.dirname(prev_export_filename))
        if filename:
            prev_export_filename = filename
            try:
                with open(filename, "w") as f:
                    for tc_name in self.tc_list_sorted:
                        tc_stats = test_db.test_case_stats[tc_name]
                        txt = "%s\t%d\t%d\t%d" % (tc_name, tc_stats[0], tc_stats[1], tc_stats[2])
                        print(txt, file=f)

            except OSError as e:
                tk_messagebox.showerror(parent=self.wid_top,
                                        message="Error writing to file: %s" % str(e))


    def __do_toggle_sort_mode(self, enable, mode):
        self.opt_sort_modes = [x for x in self.opt_sort_modes if x != mode]
        if enable:
            self.opt_sort_modes.append(mode)
        self.__handle_filter_change()


    def __do_filter_selected_tests(self, enable):
        sel = self.__get_mapped_selection()
        if len(sel) != 0:
            expr = self.test_ctrl.get_test_filter_expr()
            if enable and not expr.run_disabled():
                sel = [x for x in sel if not filter_expr.is_disabled_by_name(x)]

            self.test_ctrl.select_tcs(sel, enable)

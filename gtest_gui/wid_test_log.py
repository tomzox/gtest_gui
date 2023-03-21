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

from datetime import datetime
from enum import Enum
import bisect
import os
import re
import time

import tkinter as tk
from tkinter import messagebox as tk_messagebox

import gtest_gui.bisect
import gtest_gui.config_db as config_db
import gtest_gui.dlg_browser as dlg_browser
import gtest_gui.filter_expr as filter_expr
import gtest_gui.gtest as gtest
import gtest_gui.test_db as test_db
import gtest_gui.tk_utils as tk_utils
import gtest_gui.wid_status_line as wid_status_line
import gtest_gui.wid_test_ctrl as wid_test_ctrl
import gtest_gui.wid_text_sel as wid_text_sel


class Sort_mode(Enum):
    by_name = 0
    by_seed = 1
    by_failure = 2
    by_duration = 3


class Test_log_widget(object):
    def __init__(self, tk_top, parent):
        self.tk = tk_top
        self.test_ctrl_visible = True
        self.opt_sort_modes = []
        self.opt_filter_exe_ts = 0
        self.opt_filter_tc_names = None
        self.log_idx_map = []

        self.wid_pane = tk.PanedWindow(parent, orient=tk.VERTICAL)
        self.create_log_widget(self.wid_pane)
        self.create_trace_widget(self.wid_pane)

        test_db.Test_db_slots.result_appended = self.append_new_result
        test_db.Test_db_slots.repeat_req_update = self.update_repetition_status
        test_db.Test_db_slots.executable_update = self.refill_log


    def get_widget(self):
        return self.wid_pane


    def set_wid_test_ctrl(self, test_ctrl):
        self.test_ctrl = test_ctrl


    def create_log_widget(self, wid_pane):
        wid_frm = tk.Frame(wid_pane)
        wid_txt = tk.Text(wid_frm, width=1, height=20, font=tk_utils.font_content, wrap=tk.NONE,
                          exportselection=0, insertofftime=0, cursor="top_left_arrow")
        wid_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        wid_sb = tk.Scrollbar(wid_frm, orient=tk.VERTICAL, command=wid_txt.yview, takefocus=0)
        wid_sb.pack(side=tk.LEFT, fill=tk.Y)
        wid_txt.configure(yscrollcommand=wid_sb.set)

        wid_txt.tag_configure("highlight", font=tk_utils.font_bold, foreground="#2020A0")

        wid_txt.bindtags([wid_txt, self.tk, "TextSel", "all"])
        wid_txt.bind("<ButtonRelease-3>", lambda e: self.post_context_menu(e.widget, e.x, e.y))
        wid_txt.bind("<Double-Button-1>", lambda e: tk_utils.bind_call_and_break(self.do_open_trace_browser))
        wid_txt.bind("<Key-Return>", lambda e: self.do_open_trace_browser())
        wid_txt.bind("<Key-Delete>", lambda e: self.do_remove_selected_results())

        self.sel_obj = wid_text_sel.Text_sel_wid(wid_txt,
                                                 self.handle_selection_change, self.get_len)

        if config_db.log_pane_height:
            wid_pane.add(wid_frm, sticky="news", height=config_db.log_pane_height)
        else:
            wid_pane.add(wid_frm, sticky="news")

        wid_frm.bind("<Configure>", lambda e: self.window_resized(True, e.height))
        self.wid_log = wid_txt
        self.wid_frm1 = wid_frm


    def create_trace_widget(self, wid_pane):
        wid_frm = tk.Frame(wid_pane)
        wid_txt = tk.Text(wid_frm, width=40, height=1, wrap=tk.NONE,
                          insertofftime=0, font=tk_utils.font_content)
        wid_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        wid_txt.bindtags([wid_txt, "TextReadOnly", self.tk, "all"])
        wid_txt.tag_configure("failure", background="#FF4040")
        wid_sb = tk.Scrollbar(wid_frm, orient=tk.VERTICAL, command=wid_txt.yview, takefocus=0)
        wid_sb.pack(side=tk.LEFT, fill=tk.Y)
        wid_txt.configure(yscrollcommand=wid_sb.set)

        if not config_db.trace_pane_height:
            config_db.trace_pane_height = 9 * tk_utils.font_content.metrics("linespace")
        wid_pane.add(wid_frm, sticky="news", height=config_db.trace_pane_height)

        wid_frm.bind("<Configure>", lambda e: self.window_resized(False, e.height))
        self.wid_trace = wid_txt
        self.wid_frm2 = wid_frm


    def add_menu_commands(self, wid_men):
        self.var_opt_sort_tc_name = tk.BooleanVar(self.tk, False)
        self.var_opt_sort_seed = tk.BooleanVar(self.tk, False)
        self.var_opt_sort_duration = tk.BooleanVar(self.tk, False)
        self.var_opt_sort_exception = tk.BooleanVar(self.tk, False)

        self.var_opt_filter_pass = tk.BooleanVar(self.tk, False)
        self.var_opt_filter_exe = tk.BooleanVar(self.tk, False)
        self.var_opt_filter_tc_name = tk.BooleanVar(self.tk, False)

        wid_men.add_checkbutton(label="Show only failed results",
                                command=self.toggle_verdict_filter, variable=self.var_opt_filter_pass)
        wid_men.add_checkbutton(label="Show only current results",
                                command=self.toggle_exe_filter, variable=self.var_opt_filter_exe)
        wid_men.add_checkbutton(label="Show only selected test cases",
                                command=self.toggle_tc_name_filter, variable=self.var_opt_filter_tc_name)
        wid_men.add_separator()

        wid_men.add_checkbutton(
                label="Sort by test case name",
                command=lambda: self.toggle_sort_mode(self.var_opt_sort_tc_name.get(), Sort_mode.by_name),
                variable=self.var_opt_sort_tc_name)
        wid_men.add_checkbutton(
                label="Sort by seed",
                command=lambda: self.toggle_sort_mode(self.var_opt_sort_seed.get(), Sort_mode.by_seed),
                variable=self.var_opt_sort_seed)
        wid_men.add_checkbutton(
                label="Sort by duration",
                command=lambda: self.toggle_sort_mode(self.var_opt_sort_duration.get(), Sort_mode.by_duration),
                variable=self.var_opt_sort_duration)
        wid_men.add_checkbutton(
                label="Sort by failure type",
                command=lambda: self.toggle_sort_mode(self.var_opt_sort_exception.get(), Sort_mode.by_failure),
                variable=self.var_opt_sort_exception)


    def change_font(self, font):
        #self.wid_log.configure(font=font)
        #self.wid_trace.configure(font=font)
        config_db.rc_file_update()


    def window_resized(self, is_log, height):
        if is_log:
            if self.test_ctrl_visible:
                config_db.log_pane_height = height
            else:
                config_db.log_pane_solo_height = height
        else:
            if self.test_ctrl_visible:
                config_db.trace_pane_height = height
            else:
                config_db.trace_pane_solo_height = height

        config_db.rc_file_update_after_idle()


    def toggle_test_ctrl_visible(self, visible):
        self.test_ctrl_visible = visible

        if visible:
            if config_db.log_pane_height:
                self.wid_pane.paneconfigure(self.wid_frm1, height=config_db.log_pane_height)
            if config_db.trace_pane_height:
                self.wid_pane.paneconfigure(self.wid_frm2, height=config_db.trace_pane_height)
        else:
            if config_db.log_pane_solo_height:
                self.wid_pane.paneconfigure(self.wid_frm1, height=config_db.log_pane_solo_height)
            if config_db.trace_pane_solo_height:
                self.wid_pane.paneconfigure(self.wid_frm2, height=config_db.trace_pane_solo_height)


    def get_len(self):
        return len(self.log_idx_map)


    def handle_selection_change(self, sel):
        if len(sel) == 1:
            log_idx = self.log_idx_map[sel[0]]
            self.show_trace_preview(log_idx)
        else:
            self.clear_trace_preview()


    def get_mapped_selection(self):
        sel = self.sel_obj.text_sel_get_selection()
        return [self.log_idx_map[idx] for idx in sel]


    def append_new_result(self):
        log_idx = len(test_db.test_results) - 1
        log = test_db.test_results[log_idx]

        if self.matches_filter(log):
            if self.opt_sort_modes:
                list_idx = gtest_gui.bisect.bisect_left(self.log_idx_map, log_idx,
                                                       self.get_sort_key_fn())
                self.log_idx_map.insert(list_idx, log_idx)
            else:
                self.log_idx_map.append(log_idx)
                list_idx = len(test_db.test_results) - 1

            txt = self.format_log_line(log_idx)

            line = "%d.0" % (list_idx + 1)
            self.wid_log.insert(line, *txt)

            if self.sel_obj.text_sel_get_selection():
                self.sel_obj.text_sel_adjust_insert(list_idx)
            else:
                self.wid_log.see(line)


    def update_repetition_status(self, tc_name):
        for idx in range(len(self.log_idx_map)):
            log_idx = self.log_idx_map[idx]
            log = test_db.test_results[log_idx]
            if log[0] == tc_name:
                if self.matches_filter(log):
                    self.update_log_line(idx, log_idx)
                else:
                    self.remove_log_line(idx)
                    idx -= 1


    def remove_log_line(self, list_idx):
        line_1 = "%d.0" % (idx + 1)
        line_2 = "%d.0" % (idx + 2)
        self.wid_log.delete(line_1, line_2)

        del self.log_idx_map[idx]
        self.sel_obj.text_sel_adjust_deletion(idx)

        if not self.sel_obj.text_sel_get_selection():
            self.clear_trace_preview()


    def update_log_line(self, list_idx, log_idx):
        txt = self.format_log_line(log_idx)
        line_1 = "%d.0" % (list_idx + 1)
        line_2 = "%d.0" % (list_idx + 2)

        self.wid_log.replace(line_1, line_2, *txt)
        self.sel_obj.text_sel_show_selection()


    def format_log_line(self, log_idx):
        log = test_db.test_results[log_idx]
        now = time.time()

        if not self.opt_sort_modes and (now - log[11] < 12*60*60):
            txt = datetime.fromtimestamp(log[11]).strftime("%H:%M")
        else:
            txt = datetime.fromtimestamp(log[11]).strftime("%a %d.%m %H:%M")

        if log[3] != 4:
            if log[3] == 0:
                txt += " Passed "
            elif log[3] == 2:
                txt += " Failed "
            elif log[3] == 1:
                txt += " Skipped "
            else:
                txt += " Crashed "

            txt += log[0]

            if log[1]:
                txt += ", seed " + log[1]

            if log[12]:
                txt += " under valgrind"

            duration = log[10]
            if duration:
                if duration < 10000:
                    txt += " (%d ms)" % duration
                else:
                    duration = duration // 1000
                    txt += " (%d seconds)" % duration

            if log[8] or log[9]:
                txt += " in %s, line %d" % (log[8], log[9])

            tagged_txt = [txt, []]

            rep = test_db.repeat_requests.get(log[0])
            if rep is not None:
                if rep == test_db.test_exe_ts:
                    tagged_txt.append(" (repeat with new executable)")
                else:
                    tagged_txt.append(" (repetition pending)")
                tagged_txt.append("highlight")

        else:
            txt += " Valgrind error at end of test run"
            tagged_txt = [txt, []]

        if log[13]:
            tagged_txt.append(" (imported)")
            tagged_txt.append([])

        else:
            if log[2] != test_db.test_exe_ts:
                if log[2] == 0:
                    tagged_txt.append(" (unknown executable)")
                    tagged_txt.append([])
                elif now - log[2] <= 11*60*60:
                    tagged_txt.append(datetime.fromtimestamp(log[2]).strftime(" (old exe: %H:%M:%S)"))
                    tagged_txt.append([])
                else:
                    tagged_txt.append(datetime.fromtimestamp(log[2]).strftime(" (old exe: %a %d.%m %H:%M)"))
                    tagged_txt.append([])

        tagged_txt.extend(["\n", []])
        return tagged_txt


    def populate_log(self):
        self.wid_log.delete("1.0", "end")

        logs = [idx for idx in range(len(test_db.test_results))
                    if self.matches_filter(test_db.test_results[idx])]

        self.log_idx_map = self.sort_idx_map(logs)

        for log_idx in self.log_idx_map:
            txt = self.format_log_line(log_idx)
            self.wid_log.insert("end", *txt)


    def refill_log(self, restore_view=False, restore_selection=False):
        if restore_view or restore_selection:
            prev_log = self.log_idx_map
            prev_sel = self.sel_obj.text_sel_get_selection()
            prev_log_idx = self.log_idx_map[prev_sel[0]] if prev_sel else None
            prev_yview = self.wid_log.yview()[0]
            new_sel = None

        self.populate_log()

        if restore_selection and prev_log_idx is not None:
            try:
                new_sel = self.log_idx_map.index(prev_log_idx)
            except ValueError:
                pass

        if restore_view:
            self.wid_log.yview_moveto(prev_yview)
        else:
            self.wid_log.see("end - 1 lines")

        if restore_view and (self.log_idx_map == prev_log):
            self.sel_obj.text_sel_set_selection(prev_sel)
        elif restore_selection and new_sel is not None:
            self.wid_log.see("%d.0" % (new_sel + 1))
            self.sel_obj.text_sel_set_selection([new_sel])
        else:
            self.sel_obj.text_sel_set_selection([])
            self.clear_trace_preview()


    def sort_idx_map(self, logs):
        for mode in reversed(self.opt_sort_modes):
            if mode == Sort_mode.by_name:
                logs = sorted(logs, key=lambda x: test_db.test_results[x][0])
            elif mode == Sort_mode.by_seed:
                logs = sorted(logs, key=lambda x: test_db.test_results[x][1])
            elif mode == Sort_mode.by_failure:
                logs = sorted(logs, key=lambda x: test_db.test_results[x][9])
                logs = sorted(logs, key=lambda x: test_db.test_results[x][8])
            elif mode == Sort_mode.by_duration:
                logs = sorted(logs, key=lambda x: test_db.test_results[x][10])
        return logs


    def get_sort_key_fn(self):
        if len(self.opt_sort_modes) == 1:
            mode = self.opt_sort_modes[0]
            if mode == Sort_mode.by_name:
                return lambda x: test_db.test_results[x][0]

            elif mode == Sort_mode.by_failure:
                return lambda x: (test_db.test_results[x][8], test_db.test_results[x][9])

            elif mode == Sort_mode.by_duration:
                return lambda x: test_db.test_results[x][10]

            elif mode == Sort_mode.by_seed:
                return lambda x: test_db.test_results[x][1]

        elif len(self.opt_sort_modes) > 1:
            key_idx = []
            for mode in self.opt_sort_modes:
                if mode == Sort_mode.by_name:
                    key_idx.append(0)

                elif mode == Sort_mode.by_failure:
                    key_idx.append(8)
                    key_idx.append(9)

                elif mode == Sort_mode.by_duration:
                    key_idx.append(10)

                elif mode == Sort_mode.by_seed:
                    key_idx.append(1)

            return lambda log_idx: [test_db.test_results[log_idx][x] for x in key_idx]

        return lambda x: x


    def matches_filter(self, log):
        return ( ((not self.var_opt_filter_pass.get()) or (log[3] >= 2)) and
                 ((not self.var_opt_filter_exe.get()) or (log[2] >= self.opt_filter_exe_ts)) and
                 ((not self.var_opt_filter_tc_name.get()) or (log[0] in self.opt_filter_tc_names)) )


    def toggle_verdict_filter(self):
        self.refill_log(restore_selection=True)


    def toggle_exe_filter(self, exe_ts = None):
        if not exe_ts:
            exe_ts = test_db.test_exe_ts

        self.opt_filter_exe_ts = exe_ts
        self.refill_log(restore_selection=True)


    def toggle_tc_name_filter(self, tc_names = None):
        if self.var_opt_filter_tc_name.get():
            if tc_names is None:
                tc_names = [test_db.test_results[log_idx][0]
                                for log_idx in self.get_mapped_selection()]
            if not tc_names:
                tk_messagebox.showerror(parent=self.tk, message="No results selected")
                self.var_opt_filter_tc_name.set(False)
                return

            self.opt_filter_tc_names = set(tc_names)
        else:
            self.opt_filter_tc_names = None

        self.refill_log(restore_selection=True)


    def toggle_sort_mode(self, enable, mode):
        self.opt_sort_modes = [x for x in self.opt_sort_modes if x != mode]
        if enable:
            self.opt_sort_modes.append(mode)

        self.refill_log(restore_selection=True)


    def delete_multiple_results(self, idx_list):
        idx_list = sorted(idx_list)
        # Copy items to a new list, except for those at selected indices. As the result list
        # can be rather large, this is significantly faster than deleting items in place.
        new_list = []
        rm_idx = 0
        for idx in range(len(test_db.test_results)):
            if idx == idx_list[rm_idx]:
                if rm_idx + 1 < len(idx_list):
                    rm_idx += 1
            else:
                new_list.append(test_db.test_results[idx])

        test_db.test_results = new_list
        self.refill_log()


    def delete_single_result(self, idx):
        log_idx = bisect.bisect_left(self.log_idx_map, idx)
        if (log_idx >= len(self.log_idx_map)) or (self.log_idx_map[log_idx] != idx):
            raise ValueError

        line_1 = "%d.0" % (log_idx + 1)
        line_2 = "%d.0" % (log_idx + 2)
        self.wid_log.delete(line_1, line_2)

        self.sel_obj.text_sel_adjust_deletion(log_idx)
        if not self.sel_obj.text_sel_get_selection():
            self.clear_trace_preview()

        del test_db.test_results[self.log_idx_map[log_idx]]

        new_list = self.log_idx_map[:log_idx]
        if log_idx + 1 < len(test_db.test_results):
            new_list.extend([x - 1 for x in self.log_idx_map[log_idx + 1:]])
        self.log_idx_map = new_list


    def post_context_menu(self, parent, xcoo, ycoo):
        wid_men = tk_utils.get_context_menu_widget()
        post_menu = False

        self.sel_obj.text_sel_context_selection(xcoo, ycoo)

        sel = self.get_mapped_selection()
        if sel:
            plural_s = "" if len(sel) == 1 else "s"
            sel_tc_names = []
            any_with_trace = False
            any_rep_req = False
            no_rep_req = False

            expr = self.test_ctrl.get_test_filter_expr()
            any_can_select = False
            any_can_deselect = False

            for log_idx in sel:
                log = test_db.test_results[log_idx]
                tc_name = log[0]
                sel_tc_names.append(tc_name)
                if log[4]:
                    any_with_trace = True
                if test_db.repeat_requests.get(tc_name) is not None:
                    any_rep_req = True
                else:
                    no_rep_req = True
                if expr.can_select_test(tc_name):
                    any_can_select = True
                elif expr.can_deselect_test(tc_name):
                    any_can_deselect = True

            if len(sel) == 1:
                log = test_db.test_results[sel[0]]
                if log[4]:
                    wid_men.add_command(label="Open trace of this test case",
                                        command=lambda: self.do_open_trace_browser(False))
                    wid_men.add_command(label="Open trace of complete test run",
                                        command=lambda: self.do_open_trace_browser(True))

                if log[7]:
                    wid_men.add_command(label="Extract stack trace from core dump file",
                                        command=lambda name=log[0], core=log[7]:
                                            self.do_open_stack_trace(name, core))

                if log[4] or log[7]:
                    wid_men.add_separator()

            need_sep = False
            if any_can_select:
                wid_men.add_command(label="Add selected test case%s to filter" % plural_s,
                                    command=lambda: self.test_ctrl.select_tcs(sel_tc_names, True))
                need_sep = True
            if any_can_deselect:
                wid_men.add_command(label="Remove selected test case%s from filter" % plural_s,
                                    command=lambda: self.test_ctrl.select_tcs(sel_tc_names, False))
                need_sep = True

            if no_rep_req:
                wid_men.add_command(label="Mark test case%s for repetition" % plural_s,
                                    command=lambda: self.do_request_repetition(True))
                need_sep = True
            if any_rep_req:
                wid_men.add_command(label="Clear selected repeat request%s" % plural_s,
                                    command=lambda: self.do_request_repetition(False))
                need_sep = True

            if len(sel) == 1:
                wid_men.add_command(label="Do not show result logs from this executable",
                                    command=self.do_filter_exe_ts)
                need_sep = True

            if need_sep:
                wid_men.add_separator()

            wid_men.add_command(label="Delete selected test result%s" % plural_s,
                                command=self.do_remove_selected_results)

            if any_with_trace:
                wid_men.add_command(label="Export selected trace%s into a ZIP archive" % plural_s,
                                    command=self.do_export_trace)
            post_menu = True

        need_sep = post_menu
        if len(self.log_idx_map) < len(test_db.test_results):
            if need_sep: wid_men.add_separator()
            wid_men.add_command(label="Remove all currently filtered results",
                                command=self.do_remove_filtered_results)
            need_sep = False
            post_menu = True

        for log in test_db.test_results:
            if (log[3] <= 1) and (log[2] < test_db.test_exe_ts):
                if need_sep: wid_men.add_separator()
                wid_men.add_command(label="Remove results of passed tests from old exe.",
                                    command=self.do_remove_old_pass_results)
                post_menu = True
                break

        if post_menu:
            tk_utils.post_context_menu(parent, xcoo, ycoo)


    def do_remove_selected_results(self):
        sel = self.get_mapped_selection()
        if sel:
            self.remove_trace_files(sel)
        else:
            wid_status_line.show_message("warning", "Selection is empty - nothing to remove.")


    def do_remove_old_pass_results(self):
        idx_list = []
        for idx in range(len(test_db.test_results)):
            log = test_db.test_results[idx]
            if (log[3] <= 1) and (log[2] < test_db.test_exe_ts):
                idx_list.append(idx)

        if idx_list:
            self.remove_trace_files(idx_list)
        else:
            msg = "There are no results of passed tests from old executables."
            tk_messagebox.showerror(parent=self.tk, message=msg)


    def do_remove_filtered_results(self):
        idx_list = []
        for idx in range(len(test_db.test_results)):
            log = test_db.test_results[idx]
            if not self.matches_filter(log):
                idx_list.append(idx)

        if idx_list:
            self.remove_trace_files(idx_list)
        else:
            tk_messagebox.showerror(parent=self.tk, message="There are no filtered log entries.")


    def remove_trace_files(self, idx_list):
        idx_list = sorted(idx_list)
        rm_files = set()
        rm_idx = 0
        used_files = set()
        for idx in range(len(test_db.test_results)):
            log = test_db.test_results[idx]
            if idx == idx_list[rm_idx]:
                if log[4]:
                    rm_files.add(log[4])
                if log[7]:
                    rm_files.add(log[7])
                if rm_idx + 1 < len(idx_list):
                    rm_idx += 1
            else:
                if log[4]:
                    used_files.add(log[4])
                if log[7]:
                    used_files.add(log[7])

        rm_files -= used_files
        rm_files -= gtest.gtest_ctrl.get_out_file_names()

        count = len(idx_list)
        if count == 1:
            msg = "Really remove this result log entry"
        else:
            msg = "Really remove %d result log entries" % count

        if len(rm_files) == 1:
            msg += " and their trace output file"
        elif rm_files:
            msg += " and %d trace output and core dump files" % len(rm_files)

        msg += "? (This cannot be undone.)"
        answer = tk_messagebox.askokcancel(parent=self.tk, message=msg)
        if answer:
            try:
                for file_name in rm_files:
                    os.remove(file_name);
            except OSError:
                pass

            if len(idx_list) == 1:
                self.delete_single_result(idx_list[0])
            else:
                self.delete_multiple_results(idx_list)


    def do_request_repetition(self, enable_rep):
        sel = self.get_mapped_selection()

        if not sel:
            if test_db.repeat_requests:
                return

            for idx in self.log_idx_map:
                log = test_db.test_results[idx]
                if log[3] == 2 or log[3] == 3:
                    sel.append(idx)

        for tc_name in {test_db.test_results[x][0] for x in sel}:
            if enable_rep:
                test_db.repeat_requests[tc_name] = test_db.test_case_stats[tc_name][4]
            else:
                test_db.repeat_requests.pop(tc_name, None)

            self.update_repetition_status(tc_name)


    def do_filter_exe_ts(self):
        sel = self.get_mapped_selection()
        if len(sel) == 1:
            log = test_db.test_results[sel[0]]

            self.var_opt_filter_exe.set(True)
            self.toggle_exe_filter(log[2] + 1)


    def do_export_trace(self):
        sel = self.get_mapped_selection()
        if sel:
            dlg_browser.export_traces(self.tk, sel)


    def do_open_stack_trace(self, tc_name, core_name):
        dlg_browser.show_stack_trace(self.tk, tc_name, core_name)


    def do_open_trace_browser(self, complete_trace=False):
        sel = self.get_mapped_selection()
        if len(sel) == 1:
            log = test_db.test_results[sel[0]]
            if log[4]:
                if complete_trace:
                    dlg_browser.show_trace(self.tk, log[4])
                else:
                    dlg_browser.show_trace_snippet(self.tk, log[4], log[5], log[6])
            else:
                wid_status_line.show_message("warning", "No trace available for this result")


    def show_trace_preview(self, log_idx):
        log = test_db.test_results[log_idx]
        if log[4]:
            txt = gtest.extract_trace(log[4], log[5], log[6])
            if txt:
                self.wid_trace.replace("1.0", "end", txt)
                self.wid_trace.see("end - 1 lines")

                if log[3] >= 2:
                    line = self.wid_trace.search(": Failure", "1.0")
                    if line:
                        self.wid_trace.see(line + " linestart")
                        self.wid_trace.tag_add("failure", line + " linestart", line + " lineend")

            else:
                self.clear_trace_preview()
        else:
            self.clear_trace_preview()


    def clear_trace_preview(self):
        self.wid_trace.delete("1.0", "end")
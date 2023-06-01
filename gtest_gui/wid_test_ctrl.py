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
This module implements the test control widget class.
"""

from datetime import datetime
import os
import re
import time
import sys

import tkinter as tk
from tkinter import messagebox as tk_messagebox

from gtest_gui.dlg_config import ConfigDialog
from gtest_gui.wid_status_line import StatusLineWidget
import gtest_gui.config_db as config_db
import gtest_gui.filter_expr as filter_expr
import gtest_gui.gtest_ctrl as gtest_ctrl
import gtest_gui.gtest_list_tests as gtest_list_tests
import gtest_gui.test_db as test_db
import gtest_gui.trace_db as trace_db
import gtest_gui.tk_utils as tk_utils
import gtest_gui.wid_tool_tip as wid_tool_tip


class TestControlWidget:
    """
    This class implements the upper half of the main window, containing
    options, control buttons and status display for test campaigns.
    """

    def __init__(self, tk_top, parent):
        """ Constructs an instance of the TestControlWidget within the given parent widget. """
        self.tk_top = tk_top

        self.var_men_chkb = {}
        self.wid_men_cascades = []
        self.wid_men = None
        self.prev_campaign_options = None
        self.prev_exec_status = None
        self.wid_test_log = None  # set later due to circular dependency

        self.filter_undo_history = []
        self.filter_redo_history = []
        self.filter_undo_lock = False
        self.filter_expr_error = []
        # further attributes added by sub-functions: child widgets

        self.__create_widgets(parent)

        test_db.register_slot(test_db.SlotTypes.campaign_stats_update,
                              self.__update_campaign_status)
        self.slot_filter_change = None


    def get_widget(self):
        """ Returns the root widget used by this instance. """
        return self.wid_top


    def set_wid_test_log(self, test_log):
        """
        Links the widget with the test result log widget. This link is
        currently only used for updating repetition status. The link cannot be
        set in the constructor due to circular dependency.
        """
        self.wid_test_log = test_log


    def __create_widgets(self, parent):
        # dark theme
        app_name = self.tk_top.cget("class")
        for opt in ("background {#000000}",
                    "foreground {#FFFFFF}",
                    "highlightBackground {#000000}",
                    "highlightColor {#FFE848}",
                    "Entry*background {#FFFFFF}",
                    "Entry*foreground {#000000}",
                    "Spinbox*background {#FFFFFF}",
                    "Spinbox*foreground {#000000}",
                    "Checkbutton*selectColor {#783060}",
                    "Checkbutton*activeBackground {#303030}",
                    "Checkbutton*activeForeground {#FFFFFF}",
                    "Checkbutton*cursor top_left_arrow",
                    "Button*activeBackground {#D0E028}",
                    "Button*activeForeground {#202020}",
                    "Button*background {#A0E028}",
                    "Button*foreground {#000000}",
                    "Button*highlightthickness 2",
                    "Button*cursor top_left_arrow"):
            self.tk_top.eval("option add %s.test_ctrl.*%s" % (app_name, opt))

        self.var_opt_filter = tk.StringVar(self.tk_top, "")
        self.var_opt_repetitions = tk.IntVar(self.tk_top, 1)
        self.var_opt_job_count = tk.IntVar(self.tk_top, 1)
        self.var_opt_job_runall = tk.IntVar(self.tk_top, 0)
        self.var_opt_valgrind = tk.IntVar(self.tk_top, 0)
        self.var_opt_fail_max = tk.IntVar(self.tk_top, 0)
        self.var_opt_clean_trace = tk.BooleanVar(self.tk_top, False)
        self.var_opt_clean_core = tk.BooleanVar(self.tk_top, False)
        self.var_opt_shuffle = tk.BooleanVar(self.tk_top, False)
        self.var_opt_run_disabled = tk.BooleanVar(self.tk_top, False)
        self.var_opt_break_on_fail = tk.BooleanVar(self.tk_top, False)
        self.var_opt_break_on_except = tk.BooleanVar(self.tk_top, False)

        self.wid_top = tk.Frame(parent, name="test_ctrl") # name needed for "option add"
        self.state_dep_wids = []

        wid_frm_opt = tk.Frame(self.wid_top)
        wid_frm_opt.columnconfigure(1, weight=0)
        wid_frm_opt.columnconfigure(2, weight=1)
        wid_frm_opt.columnconfigure(3, weight=0)
        wid_frm_opt.columnconfigure(4, weight=1)

        self.wid_tc_filter = \
            self.__create_filter_entry_widget(wid_frm_opt, 1, 1,
                                              1 + 4 + 2) # span spinbox & option cols
        self.__create_spinbox_widgets(wid_frm_opt, 2, 1) # occupies 4 columns
        self.__create_option_widgets(wid_frm_opt, 2, 1 + 4) # occupies 2 columns
        wid_frm_opt.pack(side=tk.TOP, fill=tk.X, expand=1)

        wid_frm_cmd = tk.Frame(self.wid_top)
        self.__create_status_widget(wid_frm_cmd, 1, 1)
        self.__create_progress_widget(wid_frm_cmd, 1, 2)
        self.__create_control_buttons(wid_frm_cmd, 1, 4)
        wid_frm_cmd.columnconfigure(3, weight=1)
        wid_frm_cmd.columnconfigure(5, weight=2)
        wid_frm_cmd.pack(side=tk.TOP, fill=tk.X, expand=1)

        self.__update_campaign_status()

        self.wid_tc_filter.focus_set()
        self.wid_top.pack(side=tk.TOP, fill=tk.X)


    def __create_filter_entry_widget(self, parent, grid_row, grid_col, grid_col_span):
        wid_lab = tk.Label(parent, text="Test filter:")
        wid_lab.grid(row=grid_row, column=grid_col, sticky="e", padx=10)
        wid_tool_tip.tool_tip_add(wid_lab, 'test_ctrl.tc_filter')

        validate_filter_cmd = self.tk_top.register(self.__validate_tc_filter)
        wid_frm = tk.Frame(parent, relief=tk.SUNKEN, borderwidth=2)
        wid_ent = tk.Entry(wid_frm, width=40, relief=tk.FLAT, borderwidth=0,
                           textvariable=self.var_opt_filter,
                           validate="key", validatecommand=(validate_filter_cmd, "%d", "%s", "%P"))
        wid_ent.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

        wid_but = tk.Button(wid_frm, image="img_drop_down", takefocus=0, borderwidth=1,
                            relief=tk.RAISED, highlightthickness=1,
                            command=self.__popup_test_case_menu)
        wid_but.pack(side=tk.LEFT, fill=tk.Y)
        wid_frm.grid(row=grid_row, column=grid_col+1, columnspan=grid_col_span,
                     sticky="we", padx=10, pady=10)

        wid_ent.bind("<Control-Key-z>",
                     lambda e: tk_utils.bind_call_and_break(self.__undo_tc_filter_edit))
        wid_ent.bind("<Control-Key-y>",
                     lambda e: tk_utils.bind_call_and_break(self.__redo_tc_filter_edit))
        wid_ent.bind("<Control-Shift-Key-z>",
                     lambda e: tk_utils.bind_call_and_break(self.__redo_tc_filter_edit))
        wid_ent.bind("<Return>", lambda e: self.check_filter_expression())
        wid_ent.bind("<Key-Down>", lambda e: self.__popup_test_case_menu())

        return wid_ent


    def __create_spinbox_widgets(self, parent, grid_row, grid_col):
        validate_int_cmd = self.tk_top.register(TestControlWidget.__validate_int)

        wid_lab = tk.Label(parent, text="Repetitions:")
        wid_lab.grid(row=grid_row, column=grid_col+0, sticky="e", padx=10)
        wid_tool_tip.tool_tip_add(wid_lab, 'test_ctrl.repetitions')
        wid_run_count = tk.Spinbox(
            parent, from_=1, to=99999, increment=1, width=6,
            textvariable=self.var_opt_repetitions,
            validate="key", validatecommand=(validate_int_cmd, "%P"))
        wid_run_count.grid(row=grid_row, column=grid_col+1, sticky="w", padx=10)

        wid_lab = tk.Label(parent, text="CPUs:")
        wid_lab.grid(row=grid_row, column=grid_col+2, sticky="e", padx=10)
        wid_tool_tip.tool_tip_add(wid_lab, 'test_ctrl.job_count')
        wid_job_count = tk.Spinbox(
            parent, from_=1, to=1024, increment=1, width=6,
            textvariable=self.var_opt_job_count,
            validate="key", validatecommand=(validate_int_cmd, "%P"))
        wid_job_count.grid(row=grid_row, column=grid_col+3, sticky="w", padx=10)
        grid_row += 1

        wid_lab = tk.Label(parent, text="Fail limit:")
        wid_lab.grid(row=grid_row, column=grid_col+0, sticky="e", padx=10)
        wid_tool_tip.tool_tip_add(wid_lab, 'test_ctrl.max_fail')
        wid_fail_limit = tk.Spinbox(
            parent, from_=0, to=99999, increment=1, width=6,
            textvariable=self.var_opt_fail_max,
            validate="key", validatecommand=(validate_int_cmd, "%P"))
        wid_fail_limit.grid(row=grid_row, column=grid_col+1, sticky="w", padx=10)

        wid_lab = tk.Label(parent, text="Ignore filter:")
        wid_lab.grid(row=grid_row, column=grid_col+2, sticky="e", padx=10)
        wid_tool_tip.tool_tip_add(wid_lab, 'test_ctrl.job_runall')
        wid_job_runall = tk.Spinbox(
            parent, from_=0, to=1024, increment=1, width=6,
            textvariable=self.var_opt_job_runall,
            validate="key", validatecommand=(validate_int_cmd, "%P"))
        wid_job_runall.grid(row=grid_row, column=grid_col+3, sticky="w", padx=10)

        # widgets that need to be disabled during running test campaign
        self.state_dep_wids.extend([wid_run_count, wid_job_count, wid_fail_limit, wid_job_runall])


    def __create_option_widgets(self, parent, grid_row, grid_col):
        wid_lab = tk.Label(parent, text="Options:")
        wid_lab.grid(row=grid_row, column=grid_col, sticky="e", padx=10)

        wid_frm = tk.Frame(parent)
        wid_opt_clean_trace = tk.Checkbutton(
            wid_frm, text="Clean traces of passed tests",
            variable=self.var_opt_clean_trace, command=self.__handle_option_change)
        if sys.platform != "win32":
            wid_opt_clean_trace.pack(side=tk.LEFT)
        wid_tool_tip.tool_tip_add(wid_opt_clean_trace, 'test_ctrl.clean_trace')

        wid_opt_clean_core = tk.Checkbutton(
            wid_frm, text="Clean core files", variable=self.var_opt_clean_core,
            command=self.__handle_option_change)
        wid_opt_clean_core.pack(side=tk.LEFT)
        wid_frm.grid(row=grid_row, column=grid_col+1, sticky="w", padx=10)
        wid_tool_tip.tool_tip_add(wid_opt_clean_core, 'test_ctrl.clean_core')
        grid_row += 1

        wid_frm = tk.Frame(parent)
        wid_opt_shuffle = tk.Checkbutton(
            wid_frm, text="Shuffle execution order", variable=self.var_opt_shuffle)
        wid_opt_shuffle.pack(side=tk.LEFT)
        wid_tool_tip.tool_tip_add(wid_opt_shuffle, 'test_ctrl.shuffle')

        wid_opt_run_disabled = tk.Checkbutton(
            wid_frm, text="Run disabled tests", variable=self.var_opt_run_disabled,
            command=self.__handle_run_disabled_change)
        wid_opt_run_disabled.pack(side=tk.LEFT, padx=10)
        wid_frm.grid(row=grid_row, column=grid_col+1, sticky="w", padx=10)
        wid_tool_tip.tool_tip_add(wid_opt_run_disabled, 'test_ctrl.run_disabled')
        grid_row += 1

        wid_frm = tk.Frame(parent)
        wid_opt_break_on_fail = tk.Checkbutton(
            wid_frm, text="Break on failure", variable=self.var_opt_break_on_fail)
        wid_opt_break_on_fail.pack(side=tk.LEFT)
        wid_tool_tip.tool_tip_add(wid_opt_break_on_fail, 'test_ctrl.break_on_fail')

        wid_opt_break_on_except = tk.Checkbutton(
            wid_frm, text="Break on exception", variable=self.var_opt_break_on_except)
        wid_opt_break_on_except.pack(side=tk.LEFT, padx=10)
        wid_frm.grid(row=grid_row, column=grid_col+1, sticky="w", padx=10)
        wid_tool_tip.tool_tip_add(wid_opt_break_on_except, 'test_ctrl.break_on_except')
        grid_row += 1

        wid_frm = tk.Frame(parent)
        wid_opt_valgrind1 = tk.Checkbutton(
            wid_frm, text="Valgrind",
            variable=self.var_opt_valgrind, offvalue=0, onvalue=1)
        wid_opt_valgrind1.pack(side=tk.LEFT)
        wid_tool_tip.tool_tip_add(wid_opt_valgrind1, 'test_ctrl.valgrind1')

        wid_opt_valgrind2 = tk.Checkbutton(
            wid_frm, text="Valgrind - 2nd option set",
            variable=self.var_opt_valgrind, offvalue=0, onvalue=2)
        wid_opt_valgrind2.pack(side=tk.LEFT)
        if sys.platform != "win32":
            wid_frm.grid(row=grid_row, column=grid_col+1, sticky="w", padx=10)
        wid_tool_tip.tool_tip_add(wid_opt_valgrind2, 'test_ctrl.valgrind2')
        grid_row += 1

        # widgets that need to be disabled during running test campaign
        self.state_dep_wids.extend([wid_opt_shuffle, wid_opt_run_disabled, wid_opt_break_on_fail,
                                    wid_opt_break_on_except, wid_opt_valgrind1, wid_opt_valgrind2])


    def __create_control_buttons(self, parent, grid_row, grid_col):
        # This method is only called within __init__
        # pylint: disable=attribute-defined-outside-init
        width = max([tk_utils.font_normal.measure(x)
                     for x in ("Run", "Stop", "Resume", "Repeat")]) + 20
        wid_frm = tk.Frame(parent)
        self.wid_cmd_run = tk.Button(
            wid_frm, image="img_run", text="Run", compound=tk.LEFT, width=width,
            command=self.start_campaign)
        self.wid_cmd_stop = tk.Button(
            wid_frm, image="img_stop", text="Stop", compound=tk.LEFT, width=width,
            command=self.stop_campaign)
        self.wid_cmd_resume = tk.Button(
            wid_frm, image="img_resume", text="Resume", compound=tk.LEFT, width=width,
            command=self.resume_campaign)
        self.wid_cmd_repeat = tk.Button(
            wid_frm, image="img_repeat", text="Repeat", compound=tk.LEFT, width=width,
            command=self.start_repetition)
        self.wid_cmd_run.pack(side=tk.LEFT, padx=5)
        self.wid_cmd_stop.pack(side=tk.LEFT, padx=5)
        self.wid_cmd_resume.pack(side=tk.LEFT, padx=5)
        self.wid_cmd_repeat.pack(side=tk.LEFT, padx=5)
        wid_frm.grid(row=grid_row, column=grid_col)


    def __create_status_widget(self, parent, grid_row, grid_col):
        # This method is only called within __init__
        # pylint: disable=attribute-defined-outside-init
        wid_frm = tk.LabelFrame(parent, text="Status", borderwidth=2, relief=tk.GROOVE)

        wid_lab = tk.Label(wid_frm, text="Running:")
        wid_lab.grid(row=1, column=0, sticky="w", padx=2)
        self.wid_stats_exec_cnt = tk.Label(wid_frm, text="0")
        self.wid_stats_exec_cnt.grid(row=1, column=1, sticky="e", padx=2)

        wid_lab = tk.Label(wid_frm, text="Passed:")
        wid_lab.grid(row=2, column=0, sticky="w", padx=2)
        self.wid_stats_pass_cnt = tk.Label(wid_frm, text="0")
        self.wid_stats_pass_cnt.grid(row=2, column=1, sticky="e", padx=2)

        wid_lab = tk.Label(wid_frm, text="Failed:")
        wid_lab.grid(row=3, column=0, sticky="w", padx=2)
        self.wid_stats_fail_cnt = tk.Label(wid_frm, text="0")
        self.wid_stats_fail_cnt.grid(row=3, column=1, sticky="e", padx=2)

        wid_noshrink = tk.Frame(wid_frm)
        wid_noshrink.grid(row=4, column=1, sticky="we")
        wid_noshrink.bind("<Configure>", lambda e:
                          TestControlWidget.__status_widget_resized(e.widget, e.width))
        wid_frm.grid(row=grid_row, column=grid_col, sticky="ns", padx=5)


    def __create_progress_widget(self, parent, grid_row, grid_col):
        # This method is only called within __init__
        # pylint: disable=attribute-defined-outside-init
        wid_frm = tk.LabelFrame(parent, text="Progress", borderwidth=2, relief=tk.GROOVE)
        self.wid_progress_frm = tk.Frame(wid_frm)
        self.wid_progress_bar = tk.Frame(self.wid_progress_frm, width=20,
                                         background="#6868FF", borderwidth=1, relief=tk.RAISED)
        self.wid_progress_frm.pack(side=tk.TOP, fill=tk.Y, expand=1)
        wid_tool_tip.tool_tip_add(wid_frm, self.__get_progress_tool_tip)
        wid_frm.grid(row=grid_row, column=grid_col, sticky="ns")


    def __get_progress_tool_tip(self, xcoo, ycoo):
        # abstract interface: unused parameter needed by other classes
        # pylint: disable=unused-argument
        totals = test_db.campaign_stats
        if not totals[4]:
            return ""

        filter_str = self.prev_campaign_options["filter_str"]
        expr = filter_expr.FilterExpr(filter_str, self.prev_campaign_options["run_disabled"])
        tc_list = expr.get_selected_tests()
        tc_exec = [test_db.test_case_stats[x][0] +
                   test_db.test_case_stats[x][1] +
                   test_db.test_case_stats[x][2] for x in tc_list]
        min_cnt = min(tc_exec)
        max_cnt = max(tc_exec)
        rep_cnt = int(self.var_opt_repetitions.get())

        if len(tc_list) > 1 and (rep_cnt > 1):
            if max_cnt < min_cnt + 2:
                txt = ("%d of %d test case runs\n%d of %d repetitions" %
                       (totals[5], totals[4], min_cnt, rep_cnt))
            else:
                txt = ("%d of %d test case runs\n%d..%d of %d repetitions" %
                       (totals[5], totals[4], min_cnt, max_cnt, rep_cnt))
        elif rep_cnt > 1:
            txt = "%d of %d repetitions" % (min_cnt, rep_cnt)
        else:
            txt = "%d of %d test case runs" % (totals[5], totals[4])

        # get stats, but ignore background jobs
        job_stats = [x for x in gtest_ctrl.gtest_ctrl.get_job_stats() if not x[2]]
        if job_stats:
            min_job_done = min([x[4] / x[5] if x[5] else 100 for x in job_stats])
            if min_job_done:
                time_delta = time.time() - totals[7]
                time_remain = time_delta / min_job_done - time_delta

                if time_remain < 2*60:
                    txt += "\n%d seconds remaining" % time_remain
                elif time_remain < 90*60:
                    txt += "\n%.1f minutes remaining" % (time_remain / 60)
                elif time_remain < 24*60*60:
                    txt += "\n%.1f hours remaining" % (time_remain / (60*60))
                else:
                    txt += "\n%.1f days remaining" % (time_remain / (24*60*60))

        return txt


    def __update_campaign_status(self):
        # Update counters in status frame
        totals = test_db.campaign_stats
        self.wid_stats_pass_cnt.configure(text="%d" % totals[0])
        self.wid_stats_fail_cnt.configure(text="%d" % (totals[1] + totals[6]))
        self.wid_stats_exec_cnt.configure(text="%d" % totals[3])

        # Update progress bar
        if totals[4]:
            max_h = self.wid_progress_frm.winfo_height()
            bar_h = min(max_h, max_h * totals[5] // totals[4])
            self.wid_progress_bar.configure(height=bar_h)
            self.wid_progress_bar.pack(side=tk.BOTTOM)
        else:
            self.wid_progress_bar.pack_forget()

        # Executable update
        if (self.prev_campaign_options and
                (self.prev_campaign_options["exe_name"] != test_db.test_exe_name)):
            self.prev_campaign_options = None
            self.wid_cmd_resume.configure(state=tk.DISABLED)

        # Update button states if campaign was started or stopped
        tests_active = bool(totals[3])
        if self.prev_exec_status != tests_active:
            if tests_active:
                self.wid_stats_pass_cnt.configure(foreground="#18FF18", font=tk_utils.font_bold)
                self.wid_stats_fail_cnt.configure(foreground="#FF1818", font=tk_utils.font_bold)

                self.wid_cmd_run.configure(cursor="top_left_arrow")
                self.wid_cmd_stop.configure(state=tk.NORMAL)
                cmd_state = tk.DISABLED

            else:
                self.wid_stats_pass_cnt.configure(foreground="#FFFFFF", font=tk_utils.font_normal)
                self.wid_stats_fail_cnt.configure(foreground="#FFFFFF", font=tk_utils.font_normal)

                self.wid_cmd_stop.configure(state=tk.DISABLED, cursor="top_left_arrow")
                cmd_state = tk.NORMAL

            for wid in [self.wid_cmd_run,
                        self.wid_cmd_repeat,
                        self.wid_tc_filter] + self.state_dep_wids:
                wid.configure(state=cmd_state)

            if tests_active or (self.prev_campaign_options is None):
                cmd_state = tk.DISABLED
            else:
                cmd_state = tk.NORMAL
            self.wid_cmd_resume.configure(state=cmd_state)

        self.prev_exec_status = tests_active


    @staticmethod
    def __status_widget_resized(wid, new_width):
        cur_width = wid.cget("width")
        if new_width > cur_width:
            wid.configure(width=new_width)


    @staticmethod
    def __validate_int(val):
        return bool(re.match(r"^\d*$", val))


    def __validate_tc_filter(self, kind, old_val, new_val):
        self.filter_expr_error.clear()
        if (new_val != old_val) and not self.filter_undo_lock:
            kind = int(kind)
            if ((not self.filter_undo_history) or
                    (kind == -1) or
                    (kind != self.filter_undo_history[-1][1])):
                self.filter_undo_history.append((old_val, kind))
            # else: combine with last item on undo stack

            self.filter_redo_history = []
        return True


    def __undo_tc_filter_edit(self):
        if self.filter_undo_history:
            elem = self.filter_undo_history.pop()
            self.filter_redo_history.append((self.var_opt_filter.get(), 0))

            self.filter_undo_lock = True
            self.var_opt_filter.set(elem[0])
            self.filter_undo_lock = False


    def __redo_tc_filter_edit(self):
        if self.filter_redo_history:
            elem = self.filter_redo_history.pop()
            self.filter_undo_history.append((self.var_opt_filter.get(), -1))

            self.filter_undo_lock = True
            self.var_opt_filter.set(elem[0])
            self.filter_undo_lock = False


    def __popup_test_case_menu(self):
        if not self.check_filter_expression():
            return

        if self.var_opt_filter.get():
            expr = filter_expr.FilterExpr(self.var_opt_filter.get(),
                                          self.var_opt_run_disabled.get())
            matches = expr.get_selected_tests()
        else:
            matches = []

        if not tk_utils.wid_exists(self.wid_men):
            self.wid_men = tk.Menu(self.tk_top, tearoff=0)
        else:
            self.wid_men.delete(0, "end")

        all_tc_names = filter_expr.get_test_list(self.var_opt_run_disabled.get())
        if all_tc_names:
            idx = 0
            for tc_suite in filter_expr.get_test_suite_names(all_tc_names):
                if idx >= len(self.wid_men_cascades):
                    self.wid_men_cascades.append(tk.Menu(self.wid_men, tearoff=0))
                self.wid_men.add_cascade(menu=self.wid_men_cascades[idx], label=tc_suite)
                self.wid_men_cascades[idx].delete(0, "end")

                # entries for enabling/disabling complete test suite
                tc_names = filter_expr.get_tests_in_test_suite(tc_suite, all_tc_names)
                all_enabled = True
                all_disabled = True
                for tc_name in tc_names:
                    if tc_name in matches:
                        all_disabled = False
                    else:
                        all_enabled = False

                if not all_enabled:
                    self.wid_men_cascades[idx].add_command(
                        label="Enable all",
                        command=lambda x=tc_names: self.select_tcs(x, True)) # pass copy to lambda
                if not all_disabled or not matches:
                    self.wid_men_cascades[idx].add_command(
                        label="Disable all",
                        command=lambda x=tc_names: self.select_tcs(x, False)) # pass copy to lambda
                self.wid_men_cascades[idx].add_separator()

                # entries for each test case
                for tc_name in tc_names:
                    if self.var_men_chkb.get(tc_name) is None:
                        self.var_men_chkb[tc_name] = tk.BooleanVar(self.tk_top, False)
                    self.wid_men_cascades[idx].add_checkbutton(
                        label=tc_name[len(tc_suite):],
                        command=lambda x=tc_name: self.__toggle_tc(x), # pass copy to lambda
                        variable=self.var_men_chkb[tc_name], onvalue=1, offvalue=0)
                    self.var_men_chkb[tc_name].set(tc_name in matches)
                idx += 1
        elif test_db.test_exe_name:
            self.wid_men.add_command(label="List of test cases is empty", state=tk.DISABLED)
        else:
            self.wid_men.add_command(label="Please set executable path via the Control menu",
                                     state=tk.DISABLED)

        wid = self.wid_tc_filter
        self.tk_top.call("tk_popup", self.wid_men,
                         wid.winfo_rootx(), wid.winfo_rooty() + wid.winfo_height(), 0)


    def __toggle_tc(self, tc_name):
        """ Add or remove a single given test case name from the test case filter expression. """
        if not gtest_ctrl.gtest_ctrl.is_active():
            expr = filter_expr.FilterExpr(self.var_opt_filter.get(),
                                          self.var_opt_run_disabled.get())
            expr.select_test_cases([tc_name], self.var_men_chkb[tc_name].get())
            self.var_opt_filter.set(expr.get_expr())
            if self.slot_filter_change:
                self.slot_filter_change(expr)
        else:
            tk_messagebox.showerror(parent=self.tk_top,
                                    message="Cannot modify filter during running campaign.")


    def select_tcs(self, tc_names, enable):
        """ Add or remove all given test case names from the test case filter expression. """
        if not gtest_ctrl.gtest_ctrl.is_active():
            expr = filter_expr.FilterExpr(self.var_opt_filter.get(),
                                          self.var_opt_run_disabled.get())
            expr.select_test_cases(tc_names, enable)
            self.var_opt_filter.set(expr.get_expr())
            if self.slot_filter_change:
                self.slot_filter_change(expr)
        else:
            tk_messagebox.showerror(parent=self.tk_top,
                                    message="Cannot modify filter during running campaign.")


    def get_test_filter_expr(self):
        """
        Create and return a test case filter expression object reflecting the
        current content of the filter entry field.
        """
        filter_str = self.var_opt_filter.get()
        return filter_expr.FilterExpr(filter_str, self.var_opt_run_disabled.get())


    def __handle_run_disabled_change(self):
        expr = filter_expr.FilterExpr(self.var_opt_filter.get(), self.var_opt_run_disabled.get())
        if self.slot_filter_change:
            self.slot_filter_change(expr)


    def register_filter_change_slot(self, func):
        """
        Register a callback that is invoked upon changes to the test case
        filter expression. At most one other widget can register the callback.
        """
        self.slot_filter_change = func


    def start_campaign(self):
        """ Start a test campaign with the current option values in the widget. """
        if gtest_ctrl.gtest_ctrl.is_active(): # block call via key binding
            return

        if not self.__check_executable_update():
            return

        # check if given test case exists - needs to be done after exe update & reading new TC list
        if not self.check_filter_expression():
            return
        if not self.__check_test_options():
            return

        self.__start_campaign_sub(self.var_opt_filter.get())


    def stop_campaign(self):
        """ Stop the currently ongoing test campaign. """
        self.wid_cmd_stop.configure(cursor="watch")
        gtest_ctrl.gtest_ctrl.stop()


    def resume_campaign(self):
        """ Resume a previously stopped test campaign with current options. """
        if gtest_ctrl.gtest_ctrl.is_active(): # block call via key binding
            return

        if self.prev_campaign_options is None:
            StatusLineWidget.get().show_message("warn", "Campaign cannot be resumed.")
            return

        if ((self.prev_campaign_options["filter_str"] != self.var_opt_filter.get()) or
                (self.prev_campaign_options["run_disabled"] != self.var_opt_run_disabled.get())):
            msg = "Test filter options have been changed. Really resume with previous filter?"
            if not tk_messagebox.askokcancel(parent=self.tk_top, message=msg):
                return

        if not os.access(test_db.test_exe_name, os.X_OK):
            msg = "Test executable does not exist or is inaccessible: " + test_db.test_exe_name
            tk_messagebox.showerror(parent=self.tk_top, message=msg)
            return

        if not self.__check_test_options():
            return

        remaining_rep_cnt = self.__calc_remaining_repetitions()
        if remaining_rep_cnt <= 0:
            tk_messagebox.showerror(
                parent=self.tk_top,
                message="The configured number of repetitions was already completed.")
            return

        self.__start_campaign_sub(self.prev_campaign_options["filter_str"],
                                  resume_rep_cnt=remaining_rep_cnt)


    def start_repetition(self):
        """
        Start a test campaign the only runs test cases marked for repetition.
        If none were marked, all failed tests are marked automatically. A
        warning is issued if the executable is still the same as in the
        original run (because for many kinds of tests this will mean result
        will be the same.)
        """
        if gtest_ctrl.gtest_ctrl.is_active(): # block call via key binding
            return

        # Mark selected tests for repetiton, if none marked yet
        if not self.wid_test_log.do_request_repetition(True):
            return

        tc_names = test_db.repeat_requests.keys()

        if not tc_names:
            tk_messagebox.showerror(
                parent=self.tk_top,
                message="Nothing to repeat: "
                        "No results selected and no repetitions requested previously.")
            return

        if not self.__check_executable_update():
            return

        current_exe_cnt = sum([test_db.repeat_requests[x] == test_db.test_exe_ts
                               for x in tc_names])
        if current_exe_cnt:
            msg = ("Really repeat %d test%s with the same executable version?" %
                   (current_exe_cnt, "s" if current_exe_cnt > 1 else ""))
            if not tk_messagebox.askokcancel(parent=self.tk_top, message=msg):
                return

            for tc_name in test_db.repeat_requests:
                if test_db.repeat_requests[tc_name] == test_db.test_exe_ts:
                    test_db.repeat_requests[tc_name] -= 1
                    self.wid_test_log.update_repetition_status(tc_name)

        if not self.__check_test_options():
            return

        # create fake pattern that selects the test cases
        self.__start_campaign_sub(":".join(tc_names), is_repeat=True)


    def __check_executable_update(self):
        if not test_db.test_exe_name:
            tk_messagebox.showerror(parent=self.tk_top,
                                    message="Please select an executable via the Control menu")
            return False

        try:
            latest_exe_ts = int(os.stat(test_db.test_exe_name).st_mtime)  # cast away fraction
        except OSError as exc:
            tk_messagebox.showerror(parent=self.tk_top,
                                    message="Test executable inaccessible: " + str(exc))
            return False

        if test_db.test_exe_ts == latest_exe_ts:
            delta = time.time() - latest_exe_ts
            if delta < 2*60:
                msg = ""
            elif delta < 90*60:
                msg = "%d minutes ago" % (delta // 60)
            elif delta < 11*60*60:
                msg = "%.1f hours ago" % (delta / (60*60))
            else:
                msg = datetime.fromtimestamp(test_db.test_exe_ts).strftime("%a %d.%m %H:%M")

            if msg:
                StatusLineWidget.get().show_message("info", "Executable compiled " + msg)

        else:
            tc_names = gtest_list_tests.gtest_list_tests()
            if tc_names is None:
                return False

            self.prev_campaign_options = None
            trace_db.release_exe_file_copy()
            test_db.update_executable(test_db.test_exe_name, latest_exe_ts, tc_names)

        return True


    def check_filter_expression(self, reset_suppressions=True):
        """
        Check if the current content of the test case filter entry field is a
        valid expression and each sub-expression matches at least one test
        case and inform the user in case of such errors.
        """
        if reset_suppressions:
            self.filter_expr_error.clear()
        is_ok, msg = filter_expr.check_pattern(self.var_opt_filter.get(),
                                               self.var_opt_run_disabled.get(),
                                               self.filter_expr_error)
        if not is_ok and msg:
            tk_messagebox.showerror(parent=self.tk_top, message=msg)

        if is_ok and self.slot_filter_change:
            expr = filter_expr.FilterExpr(self.var_opt_filter.get(),
                                          self.var_opt_run_disabled.get())
            self.slot_filter_change(expr)

        return is_ok


    def __calc_remaining_repetitions(self):
        filter_str = self.prev_campaign_options["filter_str"]
        expr = filter_expr.FilterExpr(filter_str, self.prev_campaign_options["run_disabled"])
        tc_list = expr.get_selected_tests()
        if tc_list:
            rep_cnt = int(self.var_opt_repetitions.get())

            min_cnt = min([test_db.test_case_stats[x][0] +
                           test_db.test_case_stats[x][1] +
                           test_db.test_case_stats[x][2] for x in tc_list])
            if rep_cnt > min_cnt:
                return rep_cnt - min_cnt
        return 0


    def __check_test_options(self):
        msg = ""
        try:
            msg = 'Value for "CPUs" is not a number.'
            int(self.var_opt_job_count.get())
            msg = 'Value for "Ignore filter" is not a number.'
            int(self.var_opt_job_runall.get())
            msg = 'Value for "Repetitions" is not a number.'
            int(self.var_opt_repetitions.get())
            msg = 'Value for "Fail limit" is not a number.'
            int(self.var_opt_fail_max.get())
        except ValueError:
            tk_messagebox.showerror(parent=self.tk_top, message=msg)
            return False

        if (self.var_opt_filter.get() and
                (self.var_opt_job_runall.get() >= self.var_opt_job_count.get())):
            msg = "Really ignore filter string for all test jobs?"
            answer = tk_messagebox.askokcancel(parent=self.tk_top, message=msg)
            if not answer:
                return False

        return True


    def __start_campaign_sub(self, filter_str, resume_rep_cnt=0, is_repeat=False):
        run_disabled = self.var_opt_run_disabled.get() if resume_rep_cnt == 0 \
                            else self.prev_campaign_options["run_disabled"]
        expr = filter_expr.FilterExpr(filter_str, run_disabled)
        tc_list = expr.get_selected_tests()

        valgrind_cmd = ""
        if self.var_opt_valgrind.get() == 1:
            valgrind_cmd = config_db.get_opt("cmd_valgrind1")
        elif self.var_opt_valgrind.get() == 2:
            valgrind_cmd = config_db.get_opt("cmd_valgrind2")
        if self.var_opt_valgrind.get() and not valgrind_cmd:
            if tk_messagebox.askokcancel(
                    parent=self.tk_top,
                    message="Valgrind command line is unknown. Configure now?"):
                ConfigDialog.create_dialog(self.tk_top)
            return

        clean_trace = self.var_opt_clean_trace.get()
        if clean_trace and valgrind_cmd:
            StatusLineWidget.get().show_message("warning",
                                                "Ignoring clean-trace option with valgrind")
            clean_trace = False

        if not resume_rep_cnt:
            rep_cnt = 1 if is_repeat else self.var_opt_repetitions.get()
        else:
            rep_cnt = resume_rep_cnt

        if not is_repeat:
            self.prev_campaign_options = {
                "exe_name": test_db.test_exe_name,
                "filter_str": filter_str,
                "run_disabled": run_disabled,
            }

        self.wid_cmd_run.configure(cursor="watch")

        gtest_ctrl.gtest_ctrl.start(
            self.var_opt_job_count.get(),
            self.var_opt_job_runall.get() if not is_repeat else 0,
            rep_cnt,
            filter_str,
            tc_list,
            resume_rep_cnt != 0,
            self.var_opt_run_disabled.get(),
            self.var_opt_shuffle.get(),
            valgrind_cmd,
            self.var_opt_fail_max.get(),
            clean_trace,
            self.var_opt_clean_core.get(),
            self.var_opt_break_on_fail.get(),
            self.var_opt_break_on_except.get())


    def __handle_option_change(self):
        gtest_ctrl.gtest_ctrl.update_options(self.var_opt_clean_trace.get(),
                                             self.var_opt_clean_core.get())

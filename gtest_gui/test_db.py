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

# Plain list of test case names, in order returned by test executable
test_case_names = []

# [ 0] test case name, or "" if valgrind error
# [ 1] executable name, or None if imported
# [ 2] executable timestamp, or 0 if imported
# [ 3] verdict (0: pass, 1: skipped, 2: fail, 3: crash, 4: valgrind summary error, 5:error)
# [ 4] trace file name (or None)
# [ 5] trace file offset to start of line "[ RUN ]"
# [ 6] trace length from start offset to end of line "[ OK|FAILED ]"
# [ 7] core file name (or None)
# [ 8] source code file of exception ("" if none)
# [ 9] source code line of exception (0 if none)
# [10] execution duration reported by gtest (milliseconds)
# [11] execution end time (epoch timestamp)
# [12] executed under valgrind (bool)
# [13] imported from trace file: 0: not imported, 1: auto-import; 2: command line
# [14] seed extracted from trace ("" if not configured or not found)
test_results = []

# [0] pass count
# [1] fail count
# [2] skip count
# [3] sum test durations
# [4] executable timestamp
test_case_stats = {}

# [0] pass count
# [1] fail count
# [2] skip count
# [3] running count
# [4] expected count
# [5] completed count, not including results from background jobs
# [6] meta error count (i.e. valgrind)
campaign_stats = [0, 0, 0, 0, 0, 0, 0]

# key: tc_name
# value: exe_ts of the result for which repetition was requested
repeat_requests = {}

# Timestamp and name of executable file (test target)
test_exe_ts = 0
test_exe_name = ""


class Test_db_slots(object):
    result_appended = None
    repeat_req_update = None
    campaign_stats_update = None
    campaign_stats_reset = None
    tc_stats_update = None
    tc_names_update = None
    executable_update = None


def update_executable(filename, exe_ts, tc_names):
    global test_exe_name, test_exe_ts, test_case_names, test_case_stats, repeat_requests

    tc_names_update = (test_case_names != tc_names)
    tc_exe_update = (test_exe_name != filename)

    test_exe_name = filename
    test_exe_ts = exe_ts
    test_case_names = tc_names

    for tc_name in tc_names:
        test_case_stats.setdefault(tc_name, [0, 0, 0, 0, 0])

    if tc_exe_update:
        repeat_requests = {}

    if Test_db_slots.executable_update:
        Test_db_slots.executable_update()
    if tc_names_update and Test_db_slots.tc_names_update:
        Test_db_slots.tc_names_update()
    reset_run_stats(0, False)


def import_result(log):
    global test_results
    test_results.append(log)


def add_result(log, from_bg_job):
    global test_results
    tc_name = log[0]
    verdict = log[3]

    test_results.append(log)
    if Test_db_slots.result_appended:
        Test_db_slots.result_appended()

    rep_req = repeat_requests.get(tc_name)
    if rep_req is not None and rep_req < test_exe_ts:
        repeat_requests.pop(tc_name)
        if Test_db_slots.repeat_req_update:
            Test_db_slots.repeat_req_update(tc_name)

    if verdict == 0: # pass
        campaign_stats[0] += 1
    elif verdict == 1: # skip
        campaign_stats[2] += 1
    elif (verdict == 2) or (verdict == 3): # fail or crash
        campaign_stats[1] += 1
    else:
        campaign_stats[6] += 1

    if not from_bg_job and (verdict <= 3):
        campaign_stats[5] += 1

    if Test_db_slots.campaign_stats_update:
        Test_db_slots.campaign_stats_update()

    stat = test_case_stats.get(tc_name);
    if stat is None:
        stat = [0, 0, 0, 0, 0]
        test_case_stats[tc_name] = stat
    if verdict == 1:
        stat[2] += 1
    elif verdict != 0:
        stat[1] += 1
    else:
        stat[0] += 1
    stat[3] += log[10]
    stat[4] = log[2]
    if Test_db_slots.tc_stats_update:
        Test_db_slots.tc_stats_update(tc_name)


def reset_run_stats(exp_result_cnt, is_resume):
    global campaign_stats, test_case_stats

    if not is_resume:
        campaign_stats = [0, 0, 0, 0, exp_result_cnt, 0, 0]
        for stat in test_case_stats.values():
            stat[0] = 0
            stat[1] = 0
            stat[2] = 0
            stat[3] = 0
    else:
        campaign_stats[4] = exp_result_cnt + campaign_stats[5]

    if Test_db_slots.campaign_stats_update:
        Test_db_slots.campaign_stats_update()
    if Test_db_slots.campaign_stats_reset:
        Test_db_slots.campaign_stats_reset()


def set_job_status(job_count):
    campaign_stats[3] = job_count
    if Test_db_slots.campaign_stats_update:
        Test_db_slots.campaign_stats_update()

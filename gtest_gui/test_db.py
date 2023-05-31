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
Database of test case names, test results and test campaign status.

Data may be read globally. Additions to the database go through the functions
in this module, so that registered callbacks can be invoked for notifying
various GUI modules about the change.
"""

from enum import IntEnum

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
# [7] campaign start timestamp
campaign_stats = [0, 0, 0, 0, 0, 0, 0, 0]

# key: tc_name
# value: exe_ts of the result for which repetition was requested
repeat_requests = {}

# Timestamp and name of executable file (test target)
test_exe_ts = 0
test_exe_name = ""


class SlotTypes(IntEnum):
    """ Enumeration of callback types provided for database change events. """
    result_appended = 0
    repeat_req_update = 1
    campaign_stats_update = 2
    campaign_stats_reset = 3
    tc_stats_update = 4
    tc_names_update = 5
    executable_update = 6
    slot_count = 7


# Container for event signal registration.
test_db_slots = [None] * SlotTypes.slot_count


def register_slot(slot_type, cb):
    """ Register the given callback for the given event. """
    test_db_slots[slot_type] = cb


def deregister_slot(slot_type):
    """ De-register a possibly registered callback for the given event. """
    test_db_slots[slot_type] = None


def update_executable(filename, exe_ts, tc_names):
    """ Update executable file path and timestamp and store its list of test case names. """
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

    if test_db_slots[SlotTypes.executable_update]:
        test_db_slots[SlotTypes.executable_update]()
    if tc_names_update and test_db_slots[SlotTypes.tc_names_update]:
        test_db_slots[SlotTypes.tc_names_update]()
    reset_run_stats(0, False)


def import_result(log):
    """ Append the given result log item without triggering callbacks. Used for bulk update. """
    global test_results
    test_results.append(log)


def add_result(log, from_bg_job):
    """ Append the given result log item and update campaign statistics accordingly. """
    global test_results
    tc_name = log[0]
    verdict = log[3]

    test_results.append(log)
    if test_db_slots[SlotTypes.result_appended]:
        test_db_slots[SlotTypes.result_appended]()

    rep_req = repeat_requests.get(tc_name)
    if rep_req is not None and rep_req < test_exe_ts:
        repeat_requests.pop(tc_name)
        if test_db_slots[SlotTypes.repeat_req_update]:
            test_db_slots[SlotTypes.repeat_req_update](tc_name)

    if verdict == 0: # pass
        campaign_stats[0] += 1
    elif verdict == 1: # skip
        campaign_stats[2] += 1
    elif verdict in (2, 3): # fail or crash
        campaign_stats[1] += 1
    else:
        campaign_stats[6] += 1

    if not from_bg_job and (verdict <= 3):
        campaign_stats[5] += 1

    if test_db_slots[SlotTypes.campaign_stats_update]:
        test_db_slots[SlotTypes.campaign_stats_update]()

    stat = test_case_stats.get(tc_name)
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
    if test_db_slots[SlotTypes.tc_stats_update]:
        test_db_slots[SlotTypes.tc_stats_update](tc_name)


def delete_results(idx_list):
    """
    Remove the given results at the given indices from the log. It is possible
    to delete results of an ongoing campaign. Campaign pass/fail statistics are
    however not updated by this.
    """
    # No callback is triggered by this change! Works as this originates from GUI only.
    global test_results

    if len(idx_list) > 1:
        idx_list = sorted(idx_list)
        # Copy items to a new list, except for those at selected indices. As the result list
        # can be rather large, this is significantly faster than deleting items in place.
        new_list = []
        rm_idx = 0
        # pylint: disable=consider-using-enumerate
        for idx in range(len(test_results)):
            if idx == idx_list[rm_idx]:
                if rm_idx + 1 < len(idx_list):
                    rm_idx += 1
            else:
                new_list.append(test_results[idx])

        test_results = new_list

    elif idx_list:
        del test_results[idx_list[0]]

    else:
        pass


def reset_run_stats(exp_result_cnt, is_resume):
    """ Reset campaign statistics upon start of a test campaign. """
    global campaign_stats, test_case_stats

    if not is_resume:
        campaign_stats = [0, 0, 0, 0, exp_result_cnt, 0, 0, 0]
        for stat in test_case_stats.values():
            stat[0] = 0
            stat[1] = 0
            stat[2] = 0
            stat[3] = 0
    else:
        campaign_stats[4] = exp_result_cnt + campaign_stats[5]

    if test_db_slots[SlotTypes.campaign_stats_update]:
        test_db_slots[SlotTypes.campaign_stats_update]()
    if test_db_slots[SlotTypes.campaign_stats_reset]:
        test_db_slots[SlotTypes.campaign_stats_reset]()


def set_job_status(job_count, start_time=0):
    """ Update the number of jobs working for the current test campaign. """
    campaign_stats[3] = job_count
    if start_time:
        campaign_stats[7] = start_time

    if test_db_slots[SlotTypes.campaign_stats_update]:
        test_db_slots[SlotTypes.campaign_stats_update]()


def set_repetition_request(tc_name, enable_rep):
    """ Adds or removes a repetition request for the given test case. """
    global repeat_requests

    if enable_rep:
        repeat_requests[tc_name] = test_case_stats[tc_name][4]
    else:
        repeat_requests.pop(tc_name, None)

    if test_db_slots[SlotTypes.repeat_req_update]:
        test_db_slots[SlotTypes.repeat_req_update](tc_name)

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

import errno
from io import StringIO
import os
import re
import signal
import subprocess
import sys
import threading
import time

if (os.name == "posix"): import fcntl

from tkinter import messagebox as tk_messagebox

import gtrunner.config_db as config_db
import gtrunner.test_db as test_db
import gtrunner.tk_utils as tk_utils


gtest_ctrl = None

def initialize():
    global gtest_ctrl
    gtest_ctrl = Gtest_control()


class Gtest_control(object):
    def __init__(self):
        self.__jobs = []


    def start(self, job_cnt, job_runall_cnt, rep_cnt, filter_str, tc_list, is_resume,
              run_disabled, shuffle, valgrind_cmd, maxfail, clean_trace, clean_core,
              break_on_fail, break_on_except):
        self.__max_fail = maxfail
        self.__is_valgrind = bool(valgrind_cmd)
        self.__exe_ts = test_db.test_exe_ts

        (shard_parts, shard_reps) = calc_sharding_partitioning(
                                        len(tc_list), rep_cnt, job_cnt - job_runall_cnt)
        for idx in range(job_runall_cnt):
            shard_parts.append(1)
            shard_reps.append(rep_cnt)

        part_idx = 0
        shard_idx = 0

        trace_idx = gtest_control_first_free_trace_file_idx(self.__exe_ts)
        for idx in range(job_cnt):
            if idx >= job_cnt - job_runall_cnt:
                filter_str = ""
            try:
                self.__jobs.append(Gtest_job(self, test_db.test_exe_name, self.__exe_ts,
                                             gtest_control_get_trace_file_name(self.__exe_ts, trace_idx),
                                             filter_str, run_disabled, shuffle, valgrind_cmd,
                                             clean_trace, clean_core, break_on_fail, break_on_except,
                                             shard_reps[part_idx], shard_parts[part_idx], shard_idx,
                                             idx >= job_cnt - job_runall_cnt))
            except OSError as e:
                notify_error("Failed to start jobs: " + str(e))
                break

            trace_idx += 1
            shard_idx += 1
            if shard_idx >= shard_parts[part_idx]:
                shard_idx = 0
                part_idx += 1

        test_db.reset_run_stats(len(tc_list) * rep_cnt, is_resume)
        test_db.set_job_status(len(self.__jobs))


    def stop(self):
        for job in self.__jobs:
            job.terminate()
        self.__jobs = []
        test_db.set_job_status(len(self.__jobs))


    def update_options(self, clean_trace, clean_core):
        for job in self.__jobs:
            job.update_options(clean_trace, clean_core)


    def is_active(self):
        return bool(self.__jobs)


    def get_job_stats(self):
        stats = []
        for job in self.__jobs:
            stats.append(job.get_stats())
        return stats


    def abort_job(self, pid):
        for job in self.__jobs:
            if job.get_stats()[0] == pid:
                job.abort()


    def get_out_file_names(self):
        used_files = set()
        for job in self.__jobs:
            used_files.add(job.get_out_file_name())
        return used_files


    def report_fail(self):
        if self.__max_fail:
            self.__max_fail -= 1
            if self.__max_fail <= 0:
                tk_utils.tk_top.after_idle(self.stop)


    def report_exit(self, job):
        for idx in range(len(self.__jobs)):
            if self.__jobs[idx] == job:
                del self.__jobs[idx]
                break
        test_db.set_job_status(len(self.__jobs))

        if not any([not job.is_bg_job() for job in self.__jobs]):
            tk_utils.tk_top.after_idle(self.stop)


def calc_parts_sub(pre_part, cpu_cnt, tc_cnt, rep_cnt, max_cpu_cnt):
    #print("DBG %s | %d,%d,%d,%d" % (str(pre_part), cpu_cnt, tc_cnt, rep_cnt, max_cpu_cnt))
    partitions = []
    prev_c = 0
    div = 1
    while True:
        c = int((tc_cnt + div - 1) / div)

        if c != prev_c and c <= max_cpu_cnt:
            if c > 1:
                cnt = int(cpu_cnt / c)
                part = pre_part + ([c] * cnt)
                remainder = cpu_cnt - (c * cnt)

                if remainder > 0:
                    partitions.extend(calc_parts_sub(part, remainder, tc_cnt, rep_cnt,
                                                     min(remainder, c)))
                else:
                    partitions.append(part)
            else:
                partitions.append(pre_part + [1] * cpu_cnt)

        prev_c = c
        if c <= 1:
            break
        div += 1

    if not partitions:
        partitions.append(pre_part + [cpu_cnt])

    return partitions

def calc_partitions(tc_cnt, job_cnt, rep_cnt):
    partitions = calc_parts_sub([], job_cnt, tc_cnt, rep_cnt, job_cnt)
    return partitions


def calc_repetitions(partitions, tc_cnt, rep_cnt):
    min_time = tc_cnt * rep_cnt
    min_parts = None
    min_reps = None
    for part in partitions:
        tcs = [int((tc_cnt + c - 1) / c) for c in part]

        # step #1: estimate repetiton count based on TC# relation between CPU partitions
        # (needed for reducing the number of iterations in step 2)
        tc_est = [tcs[0] / x for x in tcs]
        sum_est = sum(tc_est)
        reps = [int(rep_cnt / sum_est * x) for x in tc_est]
        tcs_rep = tcs.copy()
        for rep_idx in range(len(tcs_rep)):
            tcs_rep[rep_idx] *= reps[rep_idx]

        # step #2: distribute remaining repetitons to partitions
        for rep_idx in range(sum(reps), rep_cnt):
            min_idx = 0
            min_val = tcs_rep[0] + tcs[0]
            for idx in range(1, len(tcs)):
                if tcs_rep[idx] + tcs[idx] < min_val:
                    min_idx = idx
                    min_val = tcs_rep[idx] + tcs[idx]
            tcs_rep[min_idx] = min_val
            reps[min_idx] += 1
        new_max = max(tcs_rep)
        #print("DBG part: " + str(part) + " -> " + str(tcs) + " -> " + str(new_max))

        # among all possible sharding partitions, select that with minimum TC# per CPU
        if (new_max < min_time) or (min_parts is None):
            min_time = new_max
            min_reps = reps
            min_parts = part.copy()

    #print(("Choice: %d " % min_time) + str(min_parts) + " * " + str(min_reps))
    return (min_parts, min_reps)


def calc_sharding_partitioning(tc_cnt, rep_cnt, job_cnt):
    if tc_cnt and rep_cnt and job_cnt:
        return calc_repetitions(calc_partitions(tc_cnt, job_cnt, rep_cnt), tc_cnt, rep_cnt)
    else:
        return ([job_cnt], [rep_cnt])


def gtest_control_first_free_trace_file_idx(exe_ts):
    free_idx = 0
    for entry in os.scandir("."):
        if entry.is_file():
            match = re.match(r"^trace\.(\d+)\.(\d+)$", entry.name)
            if match:
                this_exe_ts = int(match.group(1))
                this_idx = int(match.group(2))
                if this_exe_ts == exe_ts and this_idx >= free_idx:
                    free_idx = this_idx + 1
    return free_idx


def gtest_control_get_trace_file_name(exe_ts, idx):
    return "trace.%d.%d" % (exe_ts, idx)


def notify_error(msg):
    tk_messagebox.showerror(parent=tk_utils.tk_top, message=msg)


# ----------------------------------------------------------------------------

class Gtest_job(object):
    def __init__(self, parent, exe_name, exe_ts, out_file_name,
                 filter_str, run_disabled, shuffle, valgrind_cmd,
                 clean_trace, clean_core, break_on_fail, break_on_except,
                 rep_cnt, shard_cnt, shard_idx, is_bg_job):
        self.__parent = parent
        self.__exe_ts = exe_ts
        self.__out_file_name = out_file_name
        self.__clean_trace = clean_trace
        self.__clean_core = clean_core
        self.__is_valgrind = bool(valgrind_cmd)
        self.__is_bg_job = is_bg_job
        self.__valgrind_exit = 0
        self.__tid = None
        self.__buf_data = b""
        self.__snippet_name = b""
        self.__snippet_data = b""
        self.__trailer = False
        self.__clean_trace_file = clean_trace
        self.__sum_input_trace = 0
        self.__result_cnt = 0
        self.log = ""

        cmd = []
        if valgrind_cmd:
            cmd.extend(valgrind_cmd)
        if valgrind_cmd and config_db.options["valgrind_exit"]:
            self.__valgrind_exit = 125
            cmd.append("--error-exitcode=125")
        cmd.append(exe_name)

        if rep_cnt != 1:
            cmd.append("--gtest_repeat=" + str(rep_cnt))
        if filter_str:
            cmd.append("--gtest_filter=" + filter_str)
        if run_disabled:
            cmd.append("--gtest_also_run_disabled_tests")
        if shuffle:
            cmd.append("--gtest_shuffle")
        if break_on_fail:
            cmd.append("--gtest_break_on_failure")
        if break_on_except:
            cmd.append("--gtest_catch_exceptions=0")

        env = os.environ.copy()
        env.pop("GTEST_FILTER", None)
        env.pop("GTEST_FAIL_FAST", None)
        env.pop("GTEST_ALSO_RUN_DISABLED_TESTS", None)
        env.pop("GTEST_BREAK_ON_FAILURE", None)
        env.pop("GTEST_CATCH_EXCEPTIONS", None)
        env.pop("GTEST_REPEAT", None)
        env.pop("GTEST_SHUFFLE", None)
        env.pop("GTEST_PRINT_TIME", None)
        env.pop("GTEST_OUTPUT", None)
        #env.pop("GTEST_RANDOM_SEED", None)
        #env.pop("GTEST_COLOR", None)
        #env.pop("GTEST_PRINT_UTF8", None)

        # Have GTest create dummy file for detecting "premature exit"
        env["TEST_PREMATURE_EXIT_FILE"] = out_file_name + ".running"

        if shard_cnt > 1:
            env["GTEST_TOTAL_SHARDS"] = str(shard_cnt)
            env["GTEST_SHARD_INDEX"] = str(shard_idx)
        else:
            env.pop("GTEST_TOTAL_SHARDS", None)
            env.pop("GTEST_SHARD_INDEX", None)

        # exceptions to be caught by caller
        self.__proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, env=env)
        if self.__proc:
            flags = fcntl.fcntl(self.__proc.stdout, fcntl.F_GETFL)
            fcntl.fcntl(self.__proc.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            self.__out_file = open(out_file_name, "wb", buffering=64*1024)

            self.__tid = tk_utils.tk_top.after(100, self.__communicate)


    def terminate(self):
        self.__proc.terminate()

        if self.__tid:
            tk_utils.tk_top.after_cancel(self.__tid)
            self.__tid = None

        try:
            os.remove(self.__out_file_name + ".running")
        except OSError:
            pass

        self.__out_file.close()
        if self.__clean_trace_file:
            try:
                os.remove(self.__out_file_name)
            except OSError as e:
                pass


    def abort(self):
        self.__proc.send_signal(signal.SIGABRT)


    def update_options(self, clean_trace, clean_core):
        self.__clean_trace = clean_trace
        self.__clean_core = clean_core


    def get_out_file_name(self):
        return self.__out_file_name


    def get_stats(self):
        return [self.__proc.pid, self.__out_file_name,
                self.__sum_input_trace, self.__result_cnt,
                self.__snippet_name.decode(errors="backslashreplace")]


    def is_bg_job(self):
        return self.__is_bg_job


    def __communicate(self):
        data = self.__proc.stdout.read(256*1024)
        if data:
            self.__sum_input_trace += len(data)
            self.__buf_data += data
            done_off = 0
            for match in re.finditer(
                  b"^\[( +RUN +| +OK +| +FAILED +| +SKIPPED +|----------|==========)\] +"
                  b"(\S+)(?:\s+\((\d+)\s*ms\))?[^\n\r]*[\r\n]",
                  self.__buf_data, re.MULTILINE):

                if b"RUN" in match.group(1):
                    self.__trace_to_file(self.__snippet_data)
                    self.__trace_to_file(self.__buf_data[done_off : match.start()])
                    self.__snippet_name = match.group(2)
                    self.__snippet_data = self.__buf_data[match.start() : match.end()]
                    self.__trailer = False

                elif b" " in match.group(1) and not self.__trailer:
                    if b"OK" in match.group(1):
                        is_failed = 0
                    elif b"SKIPPED" in match.group(1):
                        is_failed = 1
                    else:
                        is_failed = 2
                    self.__snippet_data += self.__buf_data[done_off : match.end()]
                    self.__process_trace(match.group(2), is_failed, match.group(3), None)
                    self.__snippet_data = b""
                    self.__snippet_name = b""

                else:
                    self.__trace_to_file(self.__snippet_data)
                    self.__trace_to_file(self.__buf_data[done_off : match.end()])
                    self.__snippet_data = b""
                    self.__snippet_name = b""
                    self.__trailer = True

                done_off = match.end()

            last_line_off = find_last_line_start(self.__buf_data, done_off)
            if self.__snippet_data:
                self.__snippet_data += self.__buf_data[done_off : last_line_off]
            else:
                self.__trace_to_file(self.__buf_data[done_off : last_line_off])
            self.__buf_data = self.__buf_data[last_line_off:]
            self.__tid = tk_utils.tk_top.after(100, lambda: self.__communicate())

        else:
            retval = self.__proc.poll()
            if retval is None:
                self.__tid = tk_utils.tk_top.after(100, lambda: self.__communicate())
            else:
                self.__process_exit(retval)


    def __process_exit(self, retval):
        if retval != 0:
            # Detect core dump (POSIX only)
            try:
                if self.__clean_core:
                    os.remove("core.%d" % self.__proc.pid)
                    core_file = None
                else:
                    core_file = "core." + self.__out_file_name
                    os.rename("core.%d" % self.__proc.pid, core_file)
            except OSError as e:
                core_file = None
            # Detect crash under valgrind
            if self.__is_valgrind and not core_file:
                try:
                    if self.__clean_core:
                        os.remove("vgcore.%d" % self.__proc.pid)
                        core_file = None
                    else:
                        core_file = "vgcore." + self.__out_file_name
                        os.rename("vgcore.%d" % self.__proc.pid, core_file)
                except OSError as e:
                    core_file = None
            # Detect TEST_PREMATURE_EXIT_FILE
            try:
                os.remove(self.__out_file_name + ".running")
                aborted = True
            except OSError as e:
                aborted = False
            # Detect error reported by valgrind
            valgrind_error = self.__is_valgrind and (retval == self.__valgrind_exit)

            if core_file or aborted:
                if self.__snippet_data:
                    self.__snippet_data += self.__buf_data
                    self.__snippet_data += (b"\n[  CRASHED ] " + self.__snippet_name +
                                            b"\n[----------] Exit code: %d\n" % retval)
                    self.__process_trace(self.__snippet_name, 3, 0, core_file)
                else:
                    # crash in postamble, or missing trace of test case start?
                    self.__process_trace(b"unknown", 3, 0, core_file)
            elif valgrind_error:
                # this is a special case as we don't know which test case caused the error
                self.__process_trace(b"valgrind", 4, 0, None)
            else:
                self.__trace_to_file(self.__buf_data)

        else:
            self.__trace_to_file(self.__buf_data)

        self.__out_file.close()
        if self.__clean_trace_file:
            os.remove(self.__out_file_name)
        self.__parent.report_exit(self)


    def __process_trace(self, tc_name, is_failed, duration, core_file):
        tc_name = tc_name.decode(errors="backslashreplace")
        duration = int(duration) if duration else 0
        fail_file = ""
        fail_line = 0
        if is_failed >= 2:
            match = re.search(b"^(.*):([0-9]+): Failure", self.__snippet_data, re.MULTILINE)
            if match:
                fail_file = os.path.basename(match.group(1).decode(errors="backslashreplace"))
                fail_line = int(match.group(2))

        seed = ""
        pat = config_db.options.get("seed_regexp")
        if pat:
            try:
                match = re.search(pat.encode(), self.__snippet_data, re.MULTILINE)
                if match:
                    seed = match.group(1).decode(errors="backslashreplace")
            except:
                pass

        trace_start_off = self.__out_file.tell()
        trace_length = len(self.__snippet_data)
        store_trace = is_failed or not self.__clean_trace

        if is_failed == 4: # valgrind exit error: show complete trace
            trace_length = trace_start_off
            trace_start_off = 0

        if store_trace:
            self.__clean_trace_file = False
            self.__trace_to_file(self.__snippet_data)
        self.__result_cnt += 1

        test_db.add_result((tc_name, seed, self.__exe_ts, is_failed,
                            self.__out_file_name if store_trace else None,
                            trace_start_off, trace_length, core_file,
                            fail_file, fail_line, duration, int(time.time()),
                            self.__is_valgrind, False), self.__is_bg_job)

        if is_failed >= 2:
            self.__parent.report_fail()


    def __trace_to_file(self, data):
        # TODO catch error -> abort process
        self.__out_file.write(data)


# ----------------------------------------------------------------------------

def gtest_list_tests(pattern="", exe_file=None):
    if exe_file is None:
        exe_file = test_db.test_exe_name
    cmd = [exe_file, "--gtest_list_tests"]
    if pattern:
        cmd.append("--gtest_filter=" + pattern)
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True)
        result = proc.communicate(timeout=10)
        if proc.returncode == 0:
            tc_names = gtest_parse_test_list(result[0].rstrip())
            if not tc_names:
                msg = ('Read empty test case list from executable "--gtest_list_tests". '
                       'Continue anyway?')
                if not tk_messagebox.askokcancel(parent=tk_utils.tk_top, message=msg):
                    return None
            return tc_names
        else:
            msg = ("Gtest exited with error code %d when querying test case list: "
                          % proc.returncode) + str(result[1].rstrip())
            tk_messagebox.showerror(parent=tk_utils.tk_top, message=msg)
            return None

    except OSError as e:
        msg = "Failed to read test case list: " + str(e)
        tk_messagebox.showerror(parent=tk_utils.tk_top, message=msg)
        return None


def gtest_parse_test_list(lines):
    tc_names = []
    tc_suite = ""
    for line in lines.split("\n"):
        match = re.match(r"^([^0-9\s]\S+\.)$", line)
        if match:
            tc_suite = match.group(1)
        elif tc_suite:
            match = re.match(r"^\s+([^0-9\s]\S+)$", line)
            if match:
                tc_name = tc_suite + match.group(1)
                tc_names.append(tc_name)
            else:
                tc_suite = ""
    return tc_names


def find_last_line_start(buf, off):
    nl = b"\n"[0]
    for idx in reversed(range(off, len(buf))):
        if buf[idx] == nl:
            return idx + 1
    return off


def find_prev_line_end(buf, off):
    nl = b"\n"[0]
    for idx in reversed(range(off, len(buf))):
        if buf[idx] == nl:
            return idx
    return off


def find_next_line_end(buf, off):
    nl = b"\n"[0]
    for idx in range(off, len(buf)):
        if buf[idx] == nl:
            return idx + 1
    return off


def extract_trace(file_name, file_offs, length):
    try:
        with open(file_name, "rb") as f:
            if f.seek(file_offs) == file_offs:
                snippet = f.read(length)
                if snippet:
                    return snippet.decode(errors="backslashreplace")
            #else:
            #  print("Failed to seek in %s to %d: length %d" % (file_name, file_offs, f.seek(0, 2)), file=sys.stderr)
    except OSError as e:
      # use print as this function may be called from context of secondary threads
      print("Failed to read trace file:" + str(e), file=sys.stderr)

    return None


# ----------------------------------------------------------------------------
# TODO move into background loop as this may take a while

def gtest_import_tc_result(tc_name, is_failed, duration, snippet, start_off, file_name, file_ts):
    tc_name = tc_name.decode(errors="backslashreplace")
    if duration:
        duration = duration.decode(errors="backslashreplace")

    fail_file = ""
    fail_line = 0
    if is_failed:
        match = re.search(b"^(.*):([0-9]+): Failure", snippet, re.MULTILINE)
        if match:
            fail_file = os.path.basename(match.group(1).decode(errors="backslashreplace"))
            fail_line = int(match.group(2))

    seed = ""
    pat = config_db.options.get("seed_regexp")
    if pat:
        try:
            match = re.search(pat.encode(), snippet, re.MULTILINE)
            if match:
                seed = match.group(1).decode(errors="backslashreplace")
        except:
            pass

    if duration is None:
        duration = 0
    else:
        duration = int(duration)

    test_db.import_result((tc_name, seed, 0, is_failed, file_name, start_off, len(snippet),
                           None, fail_file, fail_line, duration, file_ts, False, True))


def gtest_import_result_file(file_name):
    file_ts = int(os.stat(file_name).st_mtime)  # cast away sub-second fraction
    with open(file_name, "rb", buffering=0) as f:
        snippet_start = 0
        snippet_name = b""
        snippet_data = b""
        is_trailer = False
        # Initializing with newline to allow preceding match with "\n", as "^" is extremely slow
        buf_data = b"\n"
        file_off = -1

        while True:
            new_data = f.read(256*1024)
            if not new_data:
                break

            buf_data += new_data
            done_off = 0
            for match in re.finditer(
                  b"\n\[( +RUN +| +OK +| +FAILED +| +SKIPPED +| +CRASHED +|----------|==========)\] +"
                  b"(\S+)(?:\s+\((\d+)\s*ms\))?",
                  buf_data):

                if b"RUN" in match.group(1):
                    snippet_name = match.group(2)
                    snippet_data = buf_data[match.start() + 1 : match.end()]
                    snippet_start = file_off + match.start() + 1
                    is_trailer = False

                elif b" " in match.group(1) and not is_trailer:
                    if b"OK" in match.group(1):
                        is_failed = 0
                    elif b"SKIPPED" in match.group(1):
                        is_failed = 1
                    elif b"FAILED" in match.group(1):
                        is_failed = 2
                    else:
                        is_failed = 3

                    end_off = find_next_line_end(buf_data, match.end())
                    snippet_data += buf_data[done_off : end_off]

                    gtest_import_tc_result(snippet_name, is_failed, match.group(3),
                                           snippet_data, snippet_start,
                                           file_name, file_ts)
                    snippet_name = b""
                    snippet_data = b""

                else:
                    snippet_name = b""
                    snippet_data = b""
                    is_trailer = True

                done_off = match.end()

            last_line_off = find_prev_line_end(buf_data, done_off)
            if snippet_data:
                snippet_data += buf_data[done_off : last_line_off]
            buf_data = buf_data[last_line_off:]
            file_off += last_line_off

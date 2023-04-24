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

from io import StringIO
import os
import queue
import re
import signal
import subprocess
import sys
import selectors
import threading
import time

from tkinter import messagebox as tk_messagebox

import gtest_gui.config_db as config_db
import gtest_gui.test_db as test_db
import gtest_gui.tk_utils as tk_utils
import gtest_gui.fcntl


gtest_ctrl = None

def initialize():
    global gtest_ctrl
    gtest_ctrl = Gtest_control()


class Gtest_control(object):
    def __init__(self):
        self.__jobs = []
        self.__result_queue = queue.Queue()
        self.__thr_lock = threading.Lock()
        self.__thr_inst = None
        self.__tid = None


    def start(self, job_cnt, job_runall_cnt, rep_cnt, filter_str, tc_list, is_resume,
              run_disabled, shuffle, valgrind_cmd, maxfail, clean_trace, clean_core,
              break_on_fail, break_on_except):
        self.__max_fail = maxfail
        self.__exe_ts = test_db.test_exe_ts

        trace_dir_path = gtest_control_get_trace_dir(self.__exe_ts)
        if not os.path.exists(trace_dir_path):
            try:
                os.mkdir(trace_dir_path)
            except OSError as e:
                tk_messagebox.showerror(parent=tk_utils.tk_top,
                                        message="Failed to create trace output directory: " + str(e))
                return

        exe_name = gtest_control_get_exe_file_link_name(test_db.test_exe_name, self.__exe_ts)
        if config_db.options["copy_executable"] and not os.access(exe_name, os.X_OK):
            try:
                os.link(test_db.test_exe_name, exe_name)
            except OSError as e:
                msg = ("Failed to link or copy executable: %s. Will use executable directly. "
                       "See Configuration to disable this warning.") % str(e)
                answer = tk_messagebox.showwarning(parent=tk_utils.tk_top, message=msg)
                if answer == "cancel":
                    return
                exe_name = test_db.test_exe_name

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
                self.__jobs.append(Gtest_job(self, exe_name, self.__exe_ts,
                                             gtest_control_get_trace_file_name(self.__exe_ts, trace_idx),
                                             filter_str, run_disabled, shuffle, valgrind_cmd,
                                             clean_trace, clean_core, break_on_fail, break_on_except,
                                             shard_reps[part_idx], shard_parts[part_idx], shard_idx,
                                             idx >= job_cnt - job_runall_cnt,
                                             self.__result_queue))
            except OSError as e:
                tk_messagebox.showerror(parent=tk_utils.tk_top,
                                        message="Failed to start jobs: " + str(e))
                break

            trace_idx += 1
            shard_idx += 1
            if shard_idx >= shard_parts[part_idx]:
                shard_idx = 0
                part_idx += 1

        self.__tid = tk_utils.tk_top.after(250, self.__poll_queue)

        if self.__thr_inst:
            self.__thr_inst.join(timeout=0)

        self.__thr_inst = threading.Thread(target=self.__thread_main, daemon=True)
        self.__thr_inst.start()

        test_db.reset_run_stats(len(tc_list) * rep_cnt, is_resume)
        test_db.set_job_status(len(self.__jobs))


    def __thread_main(self):
        if os.name == "posix":
            self.__thread_main_select()
        else:
            self.__thread_main_polling()


    def __thread_main_select(self):
        selector = selectors.DefaultSelector()
        with self.__thr_lock:
            for job in self.__jobs:
                selector.register(job.get_pipe(), selectors.EVENT_READ, job)

        next_poll = time.time() + 0.150
        while True:
            # Wait for EVENT_READ on any input pipe
            pending_events = selector.select()

            with self.__thr_lock:
                # Process events under lock to support abort with clean-up by main control
                if not self.__jobs:
                    return

                for event in pending_events:
                    fd = event[0].data.get_pipe()
                    if not event[0].data.communicate():
                        selector.unregister(fd)

            # Add minimum delay between reading pipes for reducing parser overhead
            sleep = next_poll - time.time()
            next_poll += 0.150

            if sleep > 0:
                time.sleep(sleep)


    def __thread_main_polling(self):
        next_poll = time.time() + 0.150
        while True:
            with self.__thr_lock:
                if not self.__jobs:
                    return

                for job in self.__jobs:
                    job.communicate()

            sleep = next_poll - time.time()
            next_poll += 0.150

            if sleep > 0:
                time.sleep(sleep)


    def __poll_queue(self):
        try:
            while True:
                result = self.__result_queue.get(block=False)
                if result[0]:
                    log = result[0]
                    if log[3] >= 2:
                        self.__report_fail()
                    test_db.add_result(result[0], result[1])
                else:
                    self.__report_exit(result[1])
        except queue.Empty:
            pass

        if self.__jobs:
            self.__tid = tk_utils.tk_top.after(250, self.__poll_queue)
        else:
            self.__tid = None


    def stop(self, kill=False):
        with self.__thr_lock:
            for job in self.__jobs:
                job.terminate(kill)

            if kill:
                self.__jobs = []


    def is_active(self):
        return bool(self.__jobs)


    def update_options(self, clean_trace, clean_core):
        with self.__thr_lock:
            for job in self.__jobs:
                job.update_options(clean_trace, clean_core)


    def get_job_stats(self):
        with self.__thr_lock:
            stats = []
            for job in self.__jobs:
                stats.append(job.get_stats())
        return stats


    def abort_job(self, pid):
        with self.__thr_lock:
            for job in self.__jobs:
                if job.get_stats()[0] == pid:
                    job.abort()


    def get_out_file_names(self):
        used_files = set()
        with self.__thr_lock:
            for job in self.__jobs:
                used_files.add(job.get_out_file_name())
        return used_files


    def __report_fail(self):
        if self.__max_fail:
            self.__max_fail -= 1
            if self.__max_fail <= 0:
                tk_utils.tk_top.after_idle(self.stop)


    def __report_exit(self, job):
        for idx in range(len(self.__jobs)):
            if self.__jobs[idx] == job:
                del self.__jobs[idx]
                break
        test_db.set_job_status(len(self.__jobs))

        with self.__thr_lock:
            have_non_bg = any([not job.is_bg_job() for job in self.__jobs])

        if not have_non_bg:
            tk_utils.tk_top.after_idle(self.stop)


# ----------------------------------------------------------------------------


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
    for entry in os.scandir(gtest_control_get_trace_dir(exe_ts)):
        if entry.is_file():
            match = re.match(r"^trace\.(\d+)$", entry.name)
            if match:
                this_idx = int(match.group(1))
                if this_idx >= free_idx:
                    free_idx = this_idx + 1
    return free_idx


def gtest_control_search_trace_dirs():
    if config_db.options["trace_dir"]:
        trace_dir_path = config_db.options["trace_dir"]
    else:
        trace_dir_path = "."

    trace_files = []
    if os.path.isdir(trace_dir_path):
        for base_entry in os.scandir(trace_dir_path):
            if re.match(r"^trace\.\d+$", base_entry.name):
                for entry in os.scandir(os.path.join(trace_dir_path, base_entry.name)):
                    if entry.is_file():
                        if re.match(r"^trace\.(\d+)$", entry.name):
                            trace_files.append(os.path.join(trace_dir_path,
                                                            base_entry.name, entry.name))

    return trace_files


def gtest_control_get_trace_dir(exe_ts):
    trace_dir_path = "trace.%d" % exe_ts
    if config_db.options["trace_dir"]:
        trace_dir_path = os.path.join(config_db.options["trace_dir"], trace_dir_path)
    return trace_dir_path


def gtest_control_get_exe_file_link_name(exe_name, exe_ts):
    if config_db.options["copy_executable"]:
        trace_dir_path = gtest_control_get_trace_dir(exe_ts)
        return os.path.join(trace_dir_path, os.path.basename(exe_name))
    else:
        return exe_name


def gtest_control_get_trace_file_name(exe_ts, idx):
    return os.path.join(gtest_control_get_trace_dir(exe_ts), "trace.%d" % idx)


def gtest_control_get_temp_name_for_trace(file_name, file_off, is_extern_import):
    if is_extern_import:
        return "imported!" + file_name.replace(os.path.sep, "!") + "." + str(file_off)
    else:
        trace_path, trace_name = os.path.split(file_name)
        return "%s.%s.%d" % (os.path.basename(trace_path), trace_name, file_off)


def gtest_control_get_core_file_name(trace_name, is_valgrind):
    split_name = os.path.split(trace_name)
    core_name = "vgcore" if is_valgrind else "core"

    return os.path.join(split_name[0], core_name + "." + split_name[1])


def release_exe_file_copy(exe_name=None, exe_ts=None):
    if exe_name is None:
        exe_name = test_db.test_exe_name
    if exe_ts is None:
        exe_ts = test_db.test_exe_ts
    if not exe_name or not exe_ts:
        return

    if not config_db.options["copy_executable"]:
        return

    trace_dir_path = gtest_control_get_trace_dir(exe_ts)
    if os.path.exists(trace_dir_path):
        dir_list = os.listdir(trace_dir_path)

        if not any([x.startswith(("core.", "vgcore.")) for x in dir_list]):
            exe_link = gtest_control_get_exe_file_link_name(exe_name, exe_ts)
            try:
                os.unlink(exe_link)
                try:
                    dir_list.remove(os.path.basename(exe_link))
                except:
                    pass
            except OSError:
                pass

            if not dir_list:
                try:
                    os.rmdir(trace_dir_path)
                except OSError:
                    pass


def remove_trace_or_core_files(rm_files, rm_exe):
    if config_db.options["copy_executable"]:
        for exe_name_ts in rm_exe:
            rm_files.add(gtest_control_get_exe_file_link_name(exe_name_ts[0], exe_name_ts[1]))

    try:
        for file_name in rm_files:
            os.remove(file_name);
    except OSError:
        pass

    rm_dirs = {os.path.dirname(x) for x in rm_files}
    for adir in rm_dirs:
        try:
            if not os.listdir(adir):
                os.rmdir(adir)
        except OSError:
            pass


def clean_all_trace_files(clean_failed=False):
    contains_fail = set()
    pass_parts = {}
    rm_files = set()
    rm_exe = set()
    for log in test_db.test_results:
        # never auto-clean imported files: could interfere with other GUI instance
        if log[4] and not log[13]:
            rm_files.add(log[4])
            if not clean_failed:
                if log[3] == 2 or log[3] == 3:
                    contains_fail.add(log[4])
                elif log[3] == 4: # valgrind: keep all pass traces
                    del pass_parts[log[4]]
                else:
                    __add_passed_section(pass_parts, log[4], log[5], log[6])

        if clean_failed and log[7]:
            rm_files.add(log[7])
            if log[1]:
                rm_exe.add((log[1], log[2]))

    if not clean_failed:
        for name in contains_fail:
            rm_files.remove(name)
            pp = pass_parts.get(name)
            if pp:
                __compress_trace_file(name, pp)

    remove_trace_or_core_files(rm_files, rm_exe)


def __add_passed_section(pass_parts, name, start, end):
    parts = pass_parts.get(name)
    if parts:
        if parts[-1][1] == start:
            parts[-1] = (pp[-1][0], end)
        else:
            pass_parts[name].append((start, end))
    else:
        pass_parts[name] = [(start, end)]


def __compress_trace_file(name, parts):
    if sys.platform == "win32":
        fd = os.open(name, os.O_RDWR | os.O_BINARY)
    else:
        fd = os.open(name, os.O_RDWR)
    size = os.stat(name).st_size
    off = parts[0][0]
    for idx in range(len(parts)):
        if idx + 1 < len(parts):
            next_start = parts[idx + 1][0]
        else:
            next_start = size
        cur_end = parts[idx][0] + parts[idx][1]

        os.lseek(fd, cur_end, os.SEEK_SET)
        data = os.read(fd, next_start - cur_end)

        os.lseek(fd, off, os.SEEK_SET)
        os.write(fd, data)

        off += len(data)
        idx += 1

    os.close(fd)
    os.truncate(name, off)



# ----------------------------------------------------------------------------

class Gtest_job(object):
    def __init__(self, parent, exe_name, exe_ts, out_file_name,
                 filter_str, run_disabled, shuffle, valgrind_cmd,
                 clean_trace, clean_core, break_on_fail, break_on_except,
                 rep_cnt, shard_cnt, shard_idx, is_bg_job, result_queue):
        self.__parent = parent
        self.__exe_name = test_db.test_exe_name
        self.__exe_ts = exe_ts
        self.__out_file_name = out_file_name
        self.__clean_trace = clean_trace
        self.__clean_core = clean_core
        self.__is_valgrind = bool(valgrind_cmd)
        self.__is_bg_job = is_bg_job
        self.__valgrind_exit = 0
        self.__result_queue = result_queue
        self.__buf_data = b""
        self.__snippet_name = b""
        self.__snippet_data = b""
        self.__trailer = False
        self.__clean_trace_file = clean_trace
        self.__sum_input_trace = 0
        self.__failed_cnt = 0
        self.__result_cnt = 0
        self.__terminated = False
        self.log = ""

        cmd = []
        if valgrind_cmd:
            cmd.extend(re.split(r"\s+", valgrind_cmd))
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
                                       stdin=subprocess.DEVNULL, env=env,
                                       creationflags=gtest_gui.fcntl.subprocess_creationflags())
        # Configure output pipe as non-blocking:
        # Caller is responsible for periodically calling communicate() to collect trace output
        flags = gtest_gui.fcntl.set_nonblocking(self.__proc.stdout)

        self.__out_file = open(out_file_name, "wb", buffering=0)


    def terminate(self, kill=False):
        if self.__proc:
            if kill or self.__terminated: # use more force in 2nd attempt
                self.__proc.kill()
            else:
                self.__proc.terminate()

            self.__terminated = True

            if kill:
                self.__close_trace_file()
                try:
                    os.remove(self.__out_file_name + ".running")
                    os.remove("vgcore.%d" % self.__proc.pid)
                    os.remove("core.%d" % self.__proc.pid)
                except OSError:
                    pass


    def abort(self):
        if self.__proc:
            if os.name == "posix":
                self.__proc.send_signal(signal.SIGABRT)
            else:
                self.__proc.terminate()


    def update_options(self, clean_trace, clean_core):
        self.__clean_trace = clean_trace
        self.__clean_core = clean_core


    def get_out_file_name(self):
        return self.__out_file_name


    def get_stats(self):
        return [self.__proc.pid if self.__proc else 0,
                self.__out_file_name,
                self.__sum_input_trace,
                self.__result_cnt,
                self.__snippet_name.decode(errors="backslashreplace")]


    def is_bg_job(self):
        return self.__is_bg_job


    def get_pipe(self):
        return self.__proc.stdout if self.__proc else None


    def communicate(self):
        if not self.__proc:
            return False

        data = gtest_gui.fcntl.read_nonblocking(self.__proc.stdout, 256*1024)

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
            return True

        else:
            retval = self.__proc.poll()
            if retval is not None:
                self.__process_exit(retval)
                self.__proc = None
                return False

            return True


    def __process_exit(self, retval):
        # Detect TEST_PREMATURE_EXIT_FILE
        try:
            os.remove(self.__out_file_name + ".running")
            aborted = True
        except OSError:
            aborted = False

        if (retval != 0 or aborted) and not self.__terminated:
            if self.__is_valgrind:
                # Detect crash under valgrind
                # (A core file from valgrind itself crashing is intentionally ignored)
                try:
                    if self.__clean_core:
                        os.remove("vgcore.%d" % self.__proc.pid)
                        core_file = None
                    else:
                        core_file = gtest_control_get_core_file_name(self.__out_file_name, True)
                        os.rename("vgcore.%d" % self.__proc.pid, core_file)
                except OSError:
                    core_file = None
            else:
                # Detect POSIX core dump file
                try:
                    if self.__clean_core:
                        os.remove("core.%d" % self.__proc.pid)
                        core_file = None
                    else:
                        core_file = gtest_control_get_core_file_name(self.__out_file_name, False)
                        os.rename("core.%d" % self.__proc.pid, core_file)
                except OSError:
                    core_file = None

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
                self.__process_trace(b"", 4, 0, None)
            elif not self.__failed_cnt:
                self.__snippet_data += self.__buf_data
                self.__snippet_data += (b"\n[----------] Exit code: %d\n" % retval)
                self.__process_trace(b"", 5, 0, None)

        else:
            self.__trace_to_file(self.__buf_data)

        self.__close_trace_file()

        # report exit to parent
        self.__result_queue.put((None, self))


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
            self.__failed_cnt += 1

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
        if store_trace:
            self.__clean_trace_file = False
            self.__trace_to_file(self.__snippet_data)

        if is_failed >= 4: # summary error: show complete trace
            trace_start_off = 0
            trace_length = self.__out_file.tell()

        self.__result_queue.put( ((tc_name, self.__exe_name, self.__exe_ts, is_failed,
                                   self.__out_file_name if store_trace else None,
                                   trace_start_off, trace_length, core_file,
                                   fail_file, fail_line, duration, int(time.time()),
                                   self.__is_valgrind, False, seed),
                                  self.__is_bg_job) )
        self.__result_cnt += 1


    def __trace_to_file(self, data):
        # TODO catch error -> abort process
        self.__out_file.write(data)


    def __close_trace_file(self):
        self.__out_file.close()
        # delete output if "clean" option, or no result log entry (i.e. file would be invisible)
        if self.__clean_trace_file or (self.__result_cnt == 0):
            os.remove(self.__out_file_name)
        self.__out_file = None


# ----------------------------------------------------------------------------

def gtest_list_tests(pattern="", exe_file=None):
    if exe_file is None:
        exe_file = test_db.test_exe_name
    cmd = [exe_file, "--gtest_list_tests"]
    if pattern:
        cmd.append("--gtest_filter=" + pattern)
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True,
                                creationflags=gtest_gui.fcntl.subprocess_creationflags())
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


def extract_trace_to_temp_file(tmp_dir, trace_name, file_offs, length, is_extern_import):
    tmp_name = os.path.join(
                    tmp_dir,
                    gtest_control_get_temp_name_for_trace(trace_name, file_offs, is_extern_import))
    if not os.path.exists(tmp_name):
        try:
            with open(trace_name, "rb") as fread:
                if fread.seek(file_offs) == file_offs:
                    with open(tmp_name, "wb") as fwrite:
                        snippet = fread.read(length)
                        fwrite.write(snippet)
        except OSError as e:
            tk_messagebox.showerror(parent=tk_utils.tk_top,
                                    message="Failed to copy trace to temporary file: " + str(e))
            tmp_name = None

    return tmp_name


# ----------------------------------------------------------------------------

def gtest_import_tc_result(tc_name, is_failed, duration, snippet, start_off,
                           file_name, file_ts, import_flag):
    tc_name = tc_name.decode(errors="backslashreplace")

    if not duration:
        duration = 0
    else:
        try:
            duration = int(duration.decode())
        except:
            duration = 0

    core_path = None
    if is_failed == 3: # CRASHED
        file_split = os.path.split(file_name)
        for with_valgrind in (False, True):
            path = os.path.join(file_split[0],
                                gtest_control_get_core_file_name(file_split[1], with_valgrind))
            if os.access(path, os.R_OK):
                core_path = path

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

    test_db.import_result((tc_name, None, 0, is_failed, file_name, start_off, len(snippet),
                           core_path, fail_file, fail_line, duration, file_ts, False,
                           import_flag, seed))


def gtest_import_result_file(file_name, is_auto):
    import_flag = 1 if is_auto else 2
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
                                           file_name, file_ts, import_flag)
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


def gtest_automatic_import():
    try:
        for file_name in gtest_control_search_trace_dirs():
            gtest_import_result_file(file_name, True)
    except OSError as e:
        tk_messagebox.showerror(parent=tk_utils.tk_top,
                                message="Error during automatic import of trace files: " + str(e))
        return

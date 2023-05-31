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
Implements Interface classes to GTest command line and trace output.
"""

import os
import queue
import re
import signal
import subprocess
import selectors
import threading
import time

from tkinter import messagebox as tk_messagebox

from gtest_gui.gtest_sharding import GtestSharding
import gtest_gui.config_db as config_db
import gtest_gui.test_db as test_db
import gtest_gui.tk_utils as tk_utils
import gtest_gui.trace_db as trace_db
import gtest_gui.fcntl


gtest_ctrl = None

def initialize():
    """ Creates the singleton instance of GtestControl. """
    global gtest_ctrl
    gtest_ctrl = GtestControl()


class GtestControl:
    """
    This class starts and controls processes spawned from the selected test
    executable for a test campaign. If offers start and stop interfaces for the
    test campaign and various status queries.
    """

    def __init__(self):
        """ Creates an idle instance of GtestControl. """
        self.__jobs = []
        self.__result_queue = queue.Queue()
        self.__thr_lock = threading.Lock()
        self.__thr_inst = None
        self.__max_fail = 0
        self.__exe_ts = None


    def start(self, job_cnt, job_runall_cnt, rep_cnt, filter_str, tc_list, is_resume,
              run_disabled, shuffle, valgrind_cmd, maxfail, clean_trace, clean_core,
              break_on_fail, break_on_except):
        """
        Start a test campaign with the given options. Errors are reported via GUI directly.
        Test results and campaign status are reported to the test results database module.
        """
        self.__max_fail = maxfail
        self.__exe_ts = test_db.test_exe_ts

        trace_dir_path = trace_db.get_trace_dir(self.__exe_ts)
        if not os.path.exists(trace_dir_path):
            try:
                os.mkdir(trace_dir_path)
            except OSError as exc:
                msg = "Failed to create trace output directory: " + str(exc)
                tk_messagebox.showerror(parent=tk_utils.tk_top, message=msg)
                return

        exe_name = trace_db.get_exe_file_link_name(test_db.test_exe_name, self.__exe_ts)
        if config_db.get_opt("copy_executable") and not os.access(exe_name, os.X_OK):
            try:
                os.link(test_db.test_exe_name, exe_name)
            except OSError as exc:
                msg = ("Failed to link or copy executable: %s. Will use executable directly. "
                       "See Configuration to disable this warning.") % str(exc)
                answer = tk_messagebox.showwarning(parent=tk_utils.tk_top, message=msg)
                if answer == "cancel":
                    return
                exe_name = test_db.test_exe_name

        sharding = GtestSharding(len(tc_list), rep_cnt, job_cnt, job_runall_cnt)

        trace_idx = trace_db.first_free_trace_file_idx(self.__exe_ts)
        for idx in range(job_cnt):
            if idx >= job_cnt - job_runall_cnt:
                filter_str = ""
            (job_rep_cnt, job_cpu_cnt, job_cpu_idx) = sharding.next()
            shard_tc_cnt = sharding.get_tc_count_per_shard(len(tc_list), job_rep_cnt,
                                                           job_cpu_cnt, job_cpu_idx)

            try:
                self.__jobs.append(GtestJob(exe_name, self.__exe_ts,
                                            trace_db.get_trace_file_name(self.__exe_ts, trace_idx),
                                            filter_str, run_disabled, shuffle, valgrind_cmd,
                                            clean_trace, clean_core,
                                            break_on_fail, break_on_except,
                                            job_rep_cnt, job_cpu_cnt, job_cpu_idx, shard_tc_cnt,
                                            idx >= job_cnt - job_runall_cnt,
                                            self.__result_queue))
            except OSError as exc:
                tk_messagebox.showerror(parent=tk_utils.tk_top,
                                        message="Failed to start jobs: " + str(exc))
                break

            trace_idx += 1

        tk_utils.tk_top.after(250, self.__poll_queue)

        # Clean up zombie processes from previous run, if any
        if self.__thr_inst:
            self.__thr_inst.join(timeout=0)

        self.__thr_inst = threading.Thread(target=self.__thread_main, daemon=True)
        self.__thr_inst.start()

        test_db.reset_run_stats(len(tc_list) * rep_cnt, is_resume)
        test_db.set_job_status(len(self.__jobs), time.time())


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
                    event_fd = event[0].data.get_pipe()
                    if not event[0].data.communicate():
                        selector.unregister(event_fd)

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
            tk_utils.tk_top.after(250, self.__poll_queue)


    def stop(self, kill=False):
        """
        Terminates all processes in the current test campaign by sending them a
        respective signal. The campaign status will not be changed to "idle"
        until the processes have been reported by the OS to have exited.  If
        parameter "kill" is True, OS will be asked to kill the process with a
        "KILL" signal that they cannot catch, on platforms that support it.
        """
        with self.__thr_lock:
            for job in self.__jobs:
                job.terminate(kill)

            if kill:
                self.__jobs = []


    def is_active(self):
        """
        Queries if a campaign is currently running. This is the case as long as
        a test process is still running.
        """
        return bool(self.__jobs)


    def update_options(self, clean_trace, clean_core):
        """
        Updates values of the "clean_trace" and "clean_core" options for a
        currently running campaign.  Changing other options than these two
        requires stopping and resuming.
        """
        with self.__thr_lock:
            for job in self.__jobs:
                job.update_options(clean_trace, clean_core)


    def get_job_stats(self):
        """ Returns a list containing status of each running test process. """
        with self.__thr_lock:
            stats = []
            for job in self.__jobs:
                stats.append(job.get_stats())
        return stats


    def abort_job(self, pid):
        """
        Sends an ABORT signal to a test process with the given PID, if it is
        still running. On POSIX systems this will result in a core dump that
        can be analyzed post-mortem, if core dumps are enabled. As a
        side-effect, the test case the process is currently executing will be
        marked as "crashed" in the result log. Other test processes are
        unaffected.
        """
        with self.__thr_lock:
            for job in self.__jobs:
                if job.get_stats()[0] == pid:
                    job.abort()


    def get_out_file_names(self):
        """
        Returns a list of output trace file names of all currently running test
        processes.  The files must not be removed via the GUI when user deletes
        results from the log in the GUI.
        """
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
            have_non_bg = any(not job.is_bg_job() for job in self.__jobs)

        if not have_non_bg:
            tk_utils.tk_top.after_idle(self.stop)


# ----------------------------------------------------------------------------

class GtestJob:
    """
    This class spawns a process from the given test executable file with the
    given GTest parameters. Afterwards it reads the trace output via a pipe.
    The pipe is read non-blocking. The caller has to periodically call the
    communicate() interface to read data from the pipe. Results are added to
    the given queue.  Process termination is reported via a special type of
    queue entry.
    """

    def __init__(self, exe_name, exe_ts, out_file_name,
                 filter_str, run_disabled, shuffle, valgrind_cmd,
                 clean_trace, clean_core, break_on_fail, break_on_except,
                 rep_cnt, shard_cnt, shard_idx, expexted_result_cnt,
                 is_bg_job, result_queue):
        """
        Spawns a new test process from the given test executable file with the
        given GTest parameters.
        """
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
        self.__expected_result_cnt = expexted_result_cnt
        self.__result_cnt = 0
        self.__terminated = False
        self.__io_error = None
        self.log = ""

        cmd = []
        if valgrind_cmd:
            cmd.extend(re.split(r"\s+", valgrind_cmd))
        if valgrind_cmd and config_db.get_opt("valgrind_exit"):
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
        gtest_gui.fcntl.set_nonblocking(self.__proc.stdout)

        self.__out_file = open(out_file_name, "wb", buffering=0)


    def terminate(self, kill=False):
        """
        Terminates the controlled process by sending it the standard termination signal.
        """
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
        """
        Terminates the controlled process by sending it an abort signal, or a
        regular termination signals on platforms that don't support abort.
        """
        if self.__proc:
            if os.name == "posix":
                self.__proc.send_signal(signal.SIGABRT)
            else:
                self.__proc.terminate()


    def update_options(self, clean_trace, clean_core):
        """
        Updates values of the "clean_trace" and "clean_core" options for a
        currently running campaign.
        """
        self.__clean_trace = clean_trace
        self.__clean_core = clean_core


    def get_out_file_name(self):
        """
        Returns the name of the output file where trace read from the process'
        pipe is stored to.
        """
        return self.__out_file_name


    def get_stats(self):
        """
        Returns statistics and parameters about the test process and trace output.
        """
        return [self.__proc.pid if self.__proc else 0,
                self.__out_file_name,
                self.__is_bg_job,
                self.__sum_input_trace,
                self.__result_cnt,
                self.__expected_result_cnt,
                self.__snippet_name.decode(errors="backslashreplace")]


    def is_bg_job(self):
        """
        Queries if the test process is configured as a "background process".
        """
        return self.__is_bg_job


    def get_pipe(self):
        """
        Returns the pipe object which connects to the test processes output.
        Returns None after the process has exited.
        """
        return self.__proc.stdout if self.__proc else None


    def communicate(self):
        """
        Check for new data in pipe connected to the test process' output and
        process it. If there is no new data, check if the process terminated.
        New results or process exit are reported to the result queue.
        """
        if not self.__proc:
            return False

        try:
            # read input from the pipe to the test process
            data = gtest_gui.fcntl.read_nonblocking(self.__proc.stdout, 256*1024)
        except OSError as exc:
            self.__io_error = "Error reading pipe from test process: " + str(exc)
            self.__proc.terminate()
            self.__terminated = True
            data = None

        if data:
            self.__process_pipe(data)
            if self.__io_error:
                self.__proc.terminate()
                self.__terminated = True
            return True

        # no data read: check if process is still alive
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
                        core_file = trace_db.get_core_file_name(self.__out_file_name, True)
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
                        core_file = trace_db.get_core_file_name(self.__out_file_name, False)
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

        elif self.__io_error:
            self.__snippet_data += (b"\n[----------] %s\n" % bytes(self.__io_error, "ascii"))
            self.__process_trace(b"", 5, 0, None)

        else:
            self.__trace_to_file(self.__buf_data)

        self.__close_trace_file()

        # report exit to parent
        self.__result_queue.put((None, self))


    def __process_pipe(self, data):
        self.__sum_input_trace += len(data)
        self.__buf_data += data
        done_off = 0
        for match in re.finditer(
                rb"^\[( +RUN +| +OK +| +FAILED +| +SKIPPED +|----------|==========)\] +"
                rb"(\S+)(?:\s+\((\d+)\s*ms\))?[^\n\r]*[\r\n]",
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

        last_line_off = _find_last_line_start(self.__buf_data, done_off)
        if self.__snippet_data:
            self.__snippet_data += self.__buf_data[done_off : last_line_off]
        else:
            self.__trace_to_file(self.__buf_data[done_off : last_line_off])
        self.__buf_data = self.__buf_data[last_line_off:]


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
        pat = config_db.get_opt("seed_regexp")
        if pat:
            try:
                match = re.search(pat.encode(), self.__snippet_data, re.MULTILINE)
                if match:
                    seed = match.group(1).decode(errors="backslashreplace")
            except (re.error, IndexError):
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

        self.__result_queue.put(((tc_name, self.__exe_name, self.__exe_ts, is_failed,
                                  self.__out_file_name if store_trace else None,
                                  trace_start_off, trace_length, core_file,
                                  fail_file, fail_line, duration, int(time.time()),
                                  self.__is_valgrind, False, seed),
                                 self.__is_bg_job))
        self.__result_cnt += 1


    def __trace_to_file(self, data):
        try:
            self.__out_file.write(data)
        except OSError as exc:
            self.__io_error = "Error writing trace output to file: " + str(exc)


    def __close_trace_file(self):
        try:
            self.__out_file.close()
        except OSError:
            pass

        # delete output if "clean" option, or no result log entry (i.e. file would be invisible)
        if self.__clean_trace_file or (self.__result_cnt == 0):
            os.remove(self.__out_file_name)
        self.__out_file = None


# ----------------------------------------------------------------------------

def _find_last_line_start(buf, off):
    nl_char = b"\n"[0]
    for idx in reversed(range(off, len(buf))):
        if buf[idx] == nl_char:
            return idx + 1
    return off


def _find_prev_line_end(buf, off):
    nl_char = b"\n"[0]
    for idx in reversed(range(off, len(buf))):
        if buf[idx] == nl_char:
            return idx
    return off


def _find_next_line_end(buf, off):
    nl_char = b"\n"[0]
    for idx in range(off, len(buf)):
        if buf[idx] == nl_char:
            return idx + 1
    return off


def _gtest_import_tc_result(tc_name, is_failed, duration, snippet, start_off,
                            file_name, file_ts, import_flag):
    tc_name = tc_name.decode(errors="backslashreplace")

    if not duration:
        duration = 0
    else:
        try:
            duration = int(duration.decode())
        except ValueError:
            duration = 0

    core_path = None
    if is_failed == 3: # CRASHED
        file_split = os.path.split(file_name)
        for with_valgrind in (False, True):
            path = os.path.join(file_split[0],
                                trace_db.get_core_file_name(file_split[1], with_valgrind))
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
    pat = config_db.get_opt("seed_regexp")
    if pat:
        try:
            match = re.search(pat.encode(), snippet, re.MULTILINE)
            if match:
                seed = match.group(1).decode(errors="backslashreplace")
        except (re.error, IndexError):
            pass

    test_db.import_result((tc_name, None, 0, is_failed, file_name, start_off, len(snippet),
                           core_path, fail_file, fail_line, duration, file_ts, False,
                           import_flag, seed))


def gtest_import_result_file(file_name, is_auto):
    """ Import test results from the given file previously written by GTest. """
    import_flag = 1 if is_auto else 2
    file_ts = int(os.stat(file_name).st_mtime)  # cast away sub-second fraction
    with open(file_name, "rb", buffering=0) as file_obj:
        snippet_start = 0
        snippet_name = b""
        snippet_data = b""
        is_trailer = False
        # Initializing with newline to allow preceding match with "\n", as "^" is extremely slow
        buf_data = b"\n"
        file_off = -1

        while True:
            new_data = file_obj.read(256*1024)
            if not new_data:
                break

            buf_data += new_data
            done_off = 0
            for match in re.finditer(
                    rb"\n\[( +RUN +| +OK +| +FAILED +| +SKIPPED +| +CRASHED +|----------|"
                    rb"==========)\] +(\S+)(?:\s+\((\d+)\s*ms\))?",
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

                    end_off = _find_next_line_end(buf_data, match.end())
                    snippet_data += buf_data[done_off : end_off]

                    _gtest_import_tc_result(snippet_name, is_failed, match.group(3),
                                            snippet_data, snippet_start,
                                            file_name, file_ts, import_flag)
                    snippet_name = b""
                    snippet_data = b""

                else:
                    snippet_name = b""
                    snippet_data = b""
                    is_trailer = True

                done_off = match.end()

            last_line_off = _find_prev_line_end(buf_data, done_off)
            if snippet_data:
                snippet_data += buf_data[done_off : last_line_off]
            buf_data = buf_data[last_line_off:]
            file_off += last_line_off


def gtest_automatic_import():
    """
    Automatically import test results from all trace files found below the
    configured trace directory.
    """
    try:
        for file_name in trace_db.search_trace_sub_dirs():
            gtest_import_result_file(file_name, True)
    except OSError as exc:
        tk_messagebox.showerror(parent=tk_utils.tk_top,
                                message="Error during automatic import of trace files: " + str(exc))
        return

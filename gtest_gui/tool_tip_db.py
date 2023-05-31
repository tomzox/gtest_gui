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
This module stores help texts to be displayed as tool tips when hovering the
mouse over GUI widgets. The database is a dict containing a unique key and
assigned help texts. The keys are used to avoid including the texts directly
within the code creating the dialogs. Note white-space in help texts is
removed before display, as the text is formatted automatically.
"""

TOOL_TIP_DB = {

    # Main window: Control menu
    'test_ctrl.cmd_start_campaign':
    '''
Resets result counters and starts a new test campaign by running the configured
executable in a process with the selected test case filter and options. If the
executable has changed since the last run, the test case list is refreshed
automatically.
''',

    'test_ctrl.cmd_stop_campaign':
    '''
Stops an ongoing test campaign by terminating the test processes. (Stop again
for killing the processes in case they do not terminated.)
''',

    'test_ctrl.cmd_resume_campaign':
    '''
Resumes a previously stopped test campaign with the same test case filter.
There will be a warning if the test case selection changed since the previous
run. Other options, such as CPU or repetition counts may be changed freely.
''',

    'test_ctrl.cmd_repeat':
    '''
Repeats the test cases marked manually for repetition via the result log, or
all previously failed test cases if none were selected. This command allows
quick repetition of individual test cases without changing the filter.
''',

    'test_ctrl.cmd_tc_list':
    '''
Open a dialog window that displays all test case names read from the configured
executable via option "--gtest_list_tests". Use the dialog's context menu for
filtering or sorting.
''',

    'test_ctrl.cmd_job_list':
    '''
Open a dialog window that displays the status of currently running test
processes. Use the dialog's context menu for aborting a process in case it is
hung.
''',

    'test_ctrl.cmd_refresh':
    '''
Reads the list of test cases from the current executable using gtest command
line option "--gtest_list_tests". Afterward, newly added test case names can be
used in test case filter.
''',

    # Main window: test case filter entry field
    'test_ctrl.tc_filter':
    '''
If not blank, only test cases matching this filter expression are run. Either
specify complete test case names, or use patterns containing "*" (matches any
string) or "?" (matches any single character). The format of a filter
expression is a ":"-separated list of wildcard patterns (positive patterns),
optionally followed by a "-" and another ":"-separated pattern list (negative
patterns). A test matches the filter if and only if it matches any of the
positive patterns, but none of the negative ones.
This entry field supports undo/redo via Control-Z and Control-Y.
''',

    # Main window: test control spinbox options
    'test_ctrl.job_count':
    '''
Number of processes to spawn which will execute tests concurrently.
Gtest\'s "sharding" feature is used for partitioning the set of test cases into
sub-sets. For small number of tests, GtestGui may additionally partition by
repetiton count for achieving better load distribution.  Due to static
partitioning, some processes may finish early if test case execution times are
non-uniform.
''',

    'test_ctrl.job_runall':
    '''
Number of test processes in which to run the full set of test cases instead of
the sub-set specified by the "Test filter" expression. The number has to be
less than that given for "CPUs". These "background" processes will be
terminated once the regular test processes have completed; Their results are
displayed normally, but they are not reflected in "Progress" reporting. Note
this feature is intended for allowing increase of repetition rate of a sub-set
of tests in long-running stress testing.
''',

    'test_ctrl.repetitions':
    'Number of times to run each test case',

    'test_ctrl.max_fail':
    '''
Stop all test processes when the given number of test failures is reached, or
never when the limit is set to 0. (Due to pipelining and concurrency, the
actual number of reported failures may exceed this value.)
''',

    # Main window: test control checkbuttons
    'test_ctrl.clean_trace':
    '''
When enabled, trace output of passed test case runs is discarded. This avoids
filling up your disk with traces when using high repetition counts.
''',

    'test_ctrl.clean_core':
    '''
When enabled, core dump files generated by crashes of the test executable are
removed from disk automatically. When not enabled, core dump files are renamed
and stack traces can be extracted via the result log.  Note this feature only
works if pattern for core files is configured as "core.%PID". The feature is
only applicable if core dumps are enabled in the kernel.
''',

    'test_ctrl.shuffle':
    '''
Sets option "--gtest_shuffle", which randomizes the order in which test cases
are executed.
''',

    'test_ctrl.run_disabled':
    '''
Sets option "--gtest_also_run_disabled_tests", which enables execution of test
cases or test suites with prefix "DISABLED" (if also matching the given test
filter expression.)
''',

    'test_ctrl.break_on_fail':
    '''
Sets option "--gtest_break_on_failure", which will have the test executable
crash with signal "TRAP" upon the first test case failure. This is useful only
when core dumps are enabled.
''',

    'test_ctrl.break_on_except':
    '''
Sets option "--gtest_catch_exceptions=0", which will have the test executable
crash when a test case throws an unhandled exception. This is useful only when
core dumps are enabled.
''',

    'test_ctrl.valgrind1':
    '''
Executes test processes under valgrind, using the valgrind command line
specified in configuration.  If valgrind detects errors, a special "valgrind"
entry is added to the result log after all test cases have run. To find which
test case caused the error, use "Open trace of complete test run" and search it
for valgrind messages (e.g. lines starting with "==").
''',

    'test_ctrl.valgrind2':
    '''
Executes test processes under valgrind, using the alternate valgrind command
line specified in configuration.
''',

    # Main window: Configuration menu
    'config.select_font_content':
    '''
Configures the font used for displaying the result log in the main window and
test case or job lists in dialog windows.
''',

    'config.select_font_trace':
    '''
Configures the font used for displaying trace output text at the bottom of the
main window.
''',

    'config.show_controls':
    '''
When unchecked, the part of the main window showing the test case filter,
options and start/stop buttons is hidden, so that there is more screen space
for the result log.  You can still start and stop test campaigns via the
control menu.
''',

    'config.show_tool_tips':
    '''
When unchecked, tool-tips like this one are globally disabled.
''',

    # Main window: Result log menu
    'result_log.filter_failed':
    '''
Show only results of failed test cases in the result log.
''',

    'result_log.filter_exe_file':
    '''
Show only results generated by the executable file currently configured as test
target. (This filter is updated when switching to a different executable.)
''',

    'result_log.filter_exe_version':
    '''
Show only results generated by the same same or newer version (i.e. timestamp)
of the currently selected executable, or the latest version if no result is
selected. The version threshold is selected only when enabling the filter;
The version threshold is not updated when starting tests with a new executable
version.
''',

    'result_log.filter_tc_name':
    '''
Show only results generated by the same test cases with the same name as
currently selected results. At least one test case in the result log needs to be
selected for enabling the filter.
''',

    'result_log.sort_tc_name':
    '''
Sort results shown in the log by test case name.
''',

    'result_log.sort_seed':
    '''
Sort results shown in the log by the "seed" value. (The seed value is a
string extracted from trace output by a freely configurable regular
expression.)
''',

    'result_log.sort_duration':
    '''
Sort results shown in the log by test case execution duration.
''',

    'result_log.sort_failure':
    '''
Sort results shown in the log by source code module and line number where
the first failure occurred.
''',


    # Configuration dialog
    'config.trowser':
    '''
Defines which application to use for opening trace snippets and complete trace
files. The file name will be appended to the given command line. The
application path or parameters must not contain spaces. The PATH configured in
environment will be used to search for the comment, so that normally the full
path need not be specified. (Note for the Windows platform, you may need to add
the Python interpreter in front of "trowser.py", depending on your Python
installation.)
''',

    'config.trowser_stdin':
    '''
Enable this if the selected trace browser supports reading text from "standard
input" via a pipeline. In this case filename "-" is passed on the command line.
The default browser "trowser" supports this. When not enabled, GtestGui has to
create temporary files for passing trace snippets to the browser application.
''',

    'config.seed':
    '''
If a regular expression pattern is specified here, it will be applied to the
trace of each test case. The string returned by the first match group (i.e.
the first set of capturing parenthesis) will be shown in the corresponding
result log as "seed". (This is intended for allowing repeat of a test sequence
exactly even for test cases using randomness, by starting their PRNG with the
same seed. This is not yet supported however, due to lack of an interface for
passing a list of seed values via the GTest command line interface.)
''',

    'config.trace_dir':
    '''
Specifies the directory where to store temporary files for trace output and
core dump files collected from the executable under test. If empty, the current
working directory at the time of starting GtestGui is used. Note
sub-directories will be created in the given directory for each executable file
version. If you want to use the "copy executable" option, the specified
directory needs to be in the same filesystem as the executables. If you want to
keep core dumps, the directory needs to be in the same filesystem as the
working directory (because they will be moved, not copied due to size.)
''',

    'config.exit_clean_trace':
    '''
When enabled, output from passed test cases is automatically removed from
created trace files upon exiting the application. Trace files and
sub-directories only containing passed test results are thus removed entirely.
Note imported trace files are never modified or removed automatically, so you
may need to remove these manually once after enabling this option (e.g. via
result log context menu).
''',

    'config.startup_import_trace':
    '''
When enabled, all trace files found in sub-directories under the configured
trace directory are read after starting GtestGui. Test case results found in
the files are shown in the result log window.
''',

    'config.copy_executable':
    '''
When enabled, a copy of the current executable under test is made within the
configured trace directory. (Technically, the copy is achieved by creating a
so-called "hard link", so that no additional disk space is needed.) This is
recommended so that recompiling the executable does not affect the current test
run (i.e. compilation may either fail with error "file busy" when tests are
running, or tests may crash). This option is required for allowing to extract
stack traces from core dump files taken from an older executable version. Note
this option may not work when using trace directories in locations such as /tmp
on UNIX-like systems, as these usually are configured to disallow executable
files for security reasons.
''',

    'config.valgrind1':
    '''
Command line to use for running test executables when the "Valgrind" option in
the main window is enabled. The executable name and gtest options will be
appended to the given command line. (Note command line parameters must not
contain spaces, as space is assumed to be separator character.)
''',

    'config.valgrind2':
    '''
Command line to use for running test executables when "Valgrind - 2nd option set"
is enabled in the main window.
''',

    'config.valgrind_exit':
    '''
When this option is set, parameter "--error-exitcode=125" will be appended to
the given valgrind command lines. This is required for detecting automatically
that valgrind found errors during test execution. Only when enabled, result
logs will report valgrind errors.
''',

    # Debug dialog
    'debug.lookup':
    '''
After clicking this button, all global variables with the prefix entered in the
entry field to the left are shown in the "Output" frame. When the field is
empty, all globals of module "dlg_main" are shown. To see globals of other
modules, enter the module name followed by a dot. To see attributes of a class
instance, type the name of the variable holding the reference followed by a
dot. When clicking on a name shown in the "Output" frame afterward, the
variable's value is shown in the "Input" frame in form of an assignment. (The
idea is that the value can then by modified by editing the content and
"Execute", however this only works for integral values and types that print
their value in form of a constructor call.)
''',

    'debug.eval':
    '''
When clicking this button, the complete content of the "Input" text entry field
is passed to Python's "eval()" function. The result is converted to a string
and shown in the "Output" frame. Note Python's "eval()" only accepts
expressions (including function calls, but not for example assignments.)
You can run this command also via key binding "Control-E".
''',

    'debug.exec':
    '''
When clicking this button, the complete content of the "Input" text entry field
is passed to Python's "exec()" function. The "Output" frame will show "None" in
case of success, or else an error or exception message. Note the output of
"print()" will be shown on the console where you started Python instead of this
window. You can run this command also via key binding "Control-X".
''',

    'debug.clear':
    '''
Clears the content of the "Output" frame.
''',

    'debug.new':
    '''
Opens a new window just as this one.
''',

}

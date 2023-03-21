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

tips = {

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
sub-sets. For small number of tests, gtest_gui may additionally partition by
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

# Configuration dialog
'config.trowser':
'''
Defines which application to use for opening trace snippets and complete trace
files. The file name will be appended to the given command line.
''',

'config.trowser_stdin':
'''
Enable this if the selected trace browser supports reading text from "standard
input" via a pipeline. In this case filename "-" is passed on the command line.
The default browser "trowser" supports this. When not enabled, gtest_gui has to
create temporary files for passing trace snippets to the browser application.
''',

'config.seed':
'''
If a regular expression pattern is specified here, it will be applied to the
trace of each test case. The string returned by the first match group (i.e.
the first set of capturing parenthesis) will be shown in the corresponding
result log as "seed". (This is intended for allowing to repeat the test case
with the same seed by passing the string as parameter to the test process; This
is not yet supported however.)
''',

'config.valgrind1':
'''
Command line to use for running test executables when the "Valgrind" option in
the main window is enabled. The executable name and gtest options will be
appended to the given command line.
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

}
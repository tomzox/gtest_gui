# GtRunner

GtRunner is a graphical user-interface to test applications using the
[GoogleTest framework](https://google.github.io/googletest/).

GtRunner is intended mainly for removing the need for fiddling with GTest
command line options, tracking the status of an ongoing test campaign and for
instant access to individual test cases' trace output.

GtRunner is designed especially for component-tests and other higher-level
testing, where the number of tests is smaller compared to unit-testing, but
individual test cases run longer and tests may have to be run repeatedly (e.g.
when test scenarios are not fully reproducible due to timing between threads.)

GtRunner supports this by allowing to schedule test cases across multiple CPUs.
For very long-running campaigns, the "clean traces of passed tests" option
allows storing only traces of failed tests to disk. Status of ongoing tests is
presented in form of a top-level pass/fail summary and progress bar, as well as
a running log of test case verdicts, which can be filtered and sorted (e.g. to
show only failed test cases.) Traces of individual test cases are accessible
while the test campaign is still running either in a small preview window below
the test log, or via double-click which exports them to an external trace
browser. ([Trowser](https://github.com/tomzox/trowser) is recommended for this
purpose.)

GtRunner provides access to GTest command line options directly from the main
window. Most importantly, test case filters can be entered manually, or via
drop-down menu listing all test cases, or the test case list dialog. Other
supported options are the test repetition count, failure limit, shuffling
execution order, running disabled tests and breaking on failure or exceptions.
The latter will on POSIX systems produce a core dump that can be pre-analyzed
via the result log's context menu by extracting stack traces. Finally, an
option allows running tests under valgrind and automatically detecting issues
that were found for the result log.

GtRunner can also be used for analyzing pre-existing trace output files
by adding the trace file names on the command line when starting.

<IMG ALIGN="center" SRC="images/screenshot_main.png" ALT="screenshot of main window" BORDER="10" WIDTH="200" />

I developed GtRunner for my daily work as a C++ software engineer. It supports
me in initial development phases using test-driven development where I need to
run the same sub-set of test cases over and over again. It supports getting a
quick overview of stability across the complete set of tests and which kind of
failures occur. And it supports final quality checking in long-running
high-repetition test campaigns, also using valgrind or sanitizer builds.

## Prerequisites

Python3 and the Python "tkinter" module are required. (The latter usually is
part of default Python installation.)

## Usage

Packages are not yet provided. To use the software, clone the repository and
then run gtrunner.py, located in the top-level directory. For integration  with
trace browser "trowser" either place "trowser.py" somewhere in the path, or
create a symlink to the path where it is located as gtrunner/trowser.

You can either specify the path of your test application directly on the
command line of gtrunner.py, or select one via a file browser afterward
(Control menu).  Alternatively, or additionally, you can specify one or more
trace output files on the command line, which will be parsed for test case
results and loaded into the result list in the GUI.

In summary, most common usage is as follows:
```console
    gtrunner/gtrunner.py my_test_application
```

On the MS-Windows platform, start GtRunner via pythonw.exe to avoid the console
window.

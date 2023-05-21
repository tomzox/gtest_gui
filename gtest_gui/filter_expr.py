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
Implements class FilterExpr for manipulating test case filter patterns.
"""

import re
import sys

import gtest_gui.test_db as test_db
import gtest_gui.tk_utils as tk_utils


class FilterExpr:
    """
    This class supports manipulating test case filter patterns in Gtest format:
    The constructor receives a filter expression, which it parses and then
    internally derives the list of matching test cases.  Interface functions
    allow retrieving this list, or querying if a given test case is currently
    selectable or deselectable. Interface functions allow adding or removing
    test cases; After such modifications the filter expression discribing the
    new list can be retrieved. The class automatically uses wildcards for
    minimizing the length of the expression.
    """
    def __init__(self, pat_str, opt_run_disabled):
        """ Constructs an intance with the given filter expression. """
        self.opt_run_disabled = opt_run_disabled
        self.pat_str = pat_str
        self.pat_list = split_gtest_filter(pat_str)
        self.matched_list = None


    def select_test_cases(self, tc_names, enable):
        """ Either adds or removes a list of test case names from the expression. """
        all_tc_names = get_test_list(self.opt_run_disabled)

        if not self.pat_list:
            if enable:
                matched = set()
            else:
                matched = set(all_tc_names)
        else:
            matched = get_matches(self.pat_list, all_tc_names)

        for tc_name in tc_names:
            if enable:
                matched.add(tc_name)
            else:
                matched.discard(tc_name)

        self.pat_list = build_expr(matched, all_tc_names)

        matched_2 = get_matches(self.pat_list, all_tc_names)
        if sorted(list(matched)) != sorted(list(matched_2)):
            print("filter_expr: failure detected for pattern:", self.pat_list,
                  "\nOrig:", matched, "\nCompressed:", matched_2, file=sys.stderr)

        self.pat_str = join_gtest_filter(self.pat_list)

        if self.pat_str:
            self.matched_list = matched
        else:
            self.matched_list = None


    def get_expr(self):
        """ Returns a filter expression describing the current sub-set of selected test cases. """
        return self.pat_str


    def get_selected_tests(self):
        """ Returns the list of all currently selected test case names. """
        if self.pat_list:
            if self.matched_list is None:
                self.matched_list = get_matches(self.pat_list, get_test_list(self.opt_run_disabled))
            return self.matched_list

        return get_test_list(self.opt_run_disabled)


    def can_select_test(self, tc_name):
        """
        Indicates if the given test case can be added to the expression. This
        is equal to the test case currently not being matched by the
        expression, or the expression bying empty.
        """
        if not self.pat_str:
            return True

        return tc_name not in self.get_selected_tests()


    def can_deselect_test(self, tc_name):
        """
        Indicates if the given test case can be removed from the expression.
        This is equal to the test case being matched by the expression.
        """
        return self.pat_str and (tc_name in self.get_selected_tests())


    def run_disabled(self):
        """ Returns the value of the "run disabled" option. """
        return self.opt_run_disabled


# ---------------------------- internal functions ----------------------------


def split_gtest_filter(pat_str):
    """
    Split a Gtest test case filter expression into two lists containing
    positive and negative expressions respectively. Normally, Gtest expressions
    should contain at most one "-", separating positive from negative
    expressions. However Gtest parser also allows multiple "-" and then toggles
    between positive and negative upon each one. This is replicated here.
    """
    pat_str = re.sub(r"\s+", "", pat_str)
    pat_str = re.sub(r"^\:+", "", pat_str)
    pat_str = re.sub(r"[\:\-]+$", "", pat_str)

    pat_list = []
    is_neg = False
    for match in re.finditer(r"([:-]+)|([^\:\-]+)", pat_str):
        if match.group(1):
            if "-" in match.group(1):
                is_neg = not is_neg
        else:
            pat = "-" if is_neg else ""
            pat += match.group(2)
            if is_neg and not pat_list:
                pat_list.append("*")
            pat_list.append(pat)

    return pat_list


def join_gtest_filter(pat_list):
    """
    Produce a Gtest filter expression from a list of positive and negative
    expressions by joining each respective list with ":" and then joining the
    results with "-".
    """
    pos_pat_list = []
    neg_pat_list = []
    for pat in pat_list:
        if pat.startswith("-"):
            neg_pat_list.append(pat[1:])
        else:
            pos_pat_list.append(pat)

    pat_str = ":".join(pos_pat_list)
    if neg_pat_list:
        pat_str += "-" + ":".join(neg_pat_list)

    return pat_str


def get_matches(pat_list, all_tc_names):
    """
    Return a sub-set of test case names from the given set that matches the
    given list of positive and negative expressions. Returned names have to
    match at least one of the positive expressions and none of the negative
    expressions.
    """
    matched = set()

    for pat in pat_list:
        if pat.startswith("-"):
            for tc_name in all_tc_names:
                if match_name(tc_name, pat[1:]):
                    matched.discard(tc_name)
        else:
            for tc_name in all_tc_names:
                if match_name(tc_name, pat):
                    matched.add(tc_name)

    return matched


def match_name(tc_name, pat):
    """
    Check if the given string matches the given pattern containing "*" and "?"
    wildcards.
    """
    # TODO convert glob pattern to regexp
    return tk_utils.tk_top.call("string", "match", pat, tc_name)


def match_name_nocase(tc_name, pat):
    """
    Check if the given string matches the given pattern containing "*" and "?"
    wildcards while ignoring case. Note this is not supported by Gtest and only
    used for generating warnings.
    """
    return tk_utils.tk_top.call("string", "match", "-nocase", pat, tc_name)


def is_disabled_by_name(tc_name):
    """
    Query if the given test case is disabled via its name as per Gtest definition.
    """
    return tc_name.startswith("DISABLED_") or (".DISABLED_" in tc_name)


def build_expr(tc_names, all_tc_names):
    """
    Return a pattern list that matches exactly the names in the first set when
    applies to the names in the second set. At worst, the result may be just a
    list of the test case names, however the function will attempt to use
    trailing wildcards and negative patterns to find a shorter representation.
    """
    if tc_names:
        tc_excluded = set()
        for tc_name in all_tc_names:
            if not tc_name in tc_names:
                tc_excluded.add(tc_name)

        return build_sub_expr(tc_names, tc_excluded, 0, True)

    return []


def build_sub_expr(tc_names, tc_excluded, min_prefix_len, allow_neg):
    """
    Helper function used by build_expr to recursively find the shortest pattern
    describing a sub-set of names. The function will use the shortest of the
    following approaches: 1. Simple list of matching names; 2. Common prefix of
    matching names followed by negative patterns describing suppression of
    excluded names; 3. Same but after splitting the list of names into multiple
    groups each having different common prefix.
    """
    result = tc_names

    if len(tc_names) > 1:
        prefix = longest_common_prefix(tc_names)
        if len(prefix) >= min_prefix_len:
            unwanted_matches = {x for x in tc_excluded if x.startswith(prefix)}

            if allow_neg or not unwanted_matches:
                min_prefix = minimize_prefix(tc_excluded - unwanted_matches, prefix, min_prefix_len)
                pat_list = [min_prefix + "*"]

                if unwanted_matches:
                    for name in build_sub_expr(unwanted_matches, tc_names, min_prefix_len, False):
                        pat_list.append("-" + name)

                if is_shorter(pat_list, result):
                    result = pat_list

            if unwanted_matches:
                sub_sets = split_at_prefix(tc_names, len(prefix))
                if sub_sets:
                    pat_list = []
                    for sub_set in sub_sets:
                        pat_list.extend(build_sub_expr(sub_set, tc_excluded,
                                                       len(prefix) + 1, allow_neg))

                    if is_shorter(pat_list, result):
                        result = pat_list

    return result


def is_shorter(pat_list_1, pat_list_2):
    """
    Compare approximate length of the resulting Gtest expression of two given
    pattern lists.
    """
    len_1 = sum([len(x) for x in pat_list_1]) + len(pat_list_1)
    len_2 = sum([len(x) for x in pat_list_2]) + len(pat_list_2)
    return len_1 < len_2


def longest_common_prefix(tc_names):
    """
    Returns the longest common prefix for the given set of names.
    """
    if not tc_names:
        return ""
    tc_names = sorted(tc_names)

    first_name = tc_names[0]
    last_name = tc_names[-1]
    prefix_len = min(len(first_name), len(last_name))

    for idx in range(prefix_len):
        if first_name[idx] != last_name[idx]:
            prefix_len = idx
            break

    return first_name[:prefix_len]


def minimize_prefix(tc_excluded, prefix, min_len):
    """
    Returns the shortest prefix of the given prefix that is not a prefix of any
    of the given names.  Or in other words: Reduces the length of the given
    prefix string until it matches one of the given names, then returns that
    length plus one.
    """
    if tc_excluded:
        if len(prefix) <= 1:
            return prefix

        for prefix_len in range(len(prefix) - 1, min_len - 1, -1):
            part = prefix[:prefix_len]
            if any(map(lambda x, part=part: x.startswith(part), tc_excluded)):
                return prefix[:prefix_len + 1]

    return prefix[:min_len]


def split_at_prefix(tc_names, prefix_len):
    """
    Splits the given set of names into sub-sets of names that each start with a
    different letter at the given index.
    """
    result = []
    if len(tc_names) > 2:
        cur_char = None
        cur_names = None
        for name in sorted(tc_names):
            if prefix_len >= len(name):
                result.append([name])
            elif cur_char is None or cur_char != name[prefix_len]:
                if cur_names:
                    result.append(cur_names)
                cur_char = name[prefix_len]
                cur_names = set([name])
            else:
                cur_names.add(name)
        if cur_names:
            result.append(cur_names)

    return result


def get_test_list(opt_run_disabled):
    """
    Returns the list of all test cases in the configured executable to be
    considered for pattern matching. The result depends on the "run disabled"
    option.
    """
    if opt_run_disabled:
        return test_db.test_case_names

    return [x for x in test_db.test_case_names if not is_disabled_by_name(x)]


def get_test_suite_names(tc_list):
    """
    Returns the list of all test suite names found in the given list of test
    case names. A test suite name is the part of the test case name up to and
    including a dot.
    """
    suites = set()
    for tc_name in tc_list:
        match = re.match(r"^([^\.]+\.)", tc_name)
        if match:
            suites.add(match.group(1))
        else:
            suites.add("")
    return sorted(list(suites))


def get_tests_in_test_suite(tc_suite, all_tc_names):
    """
    Returns a sub-set of the given test case names that are part of a given
    test suite.
    """
    if not tc_suite:
        return [x for x in all_tc_names if "." not in x]

    return [x for x in all_tc_names if x.startswith(tc_suite)]


def check_pattern(pat_str, run_disabled, suppressions=None):
    """
    Checks the given Gtest test case filter expression for regular expressions
    that do not match any test case in the current executable's set of test
    cases. Returns a warning message for the first such pattern that is found
    that should be displayed by the caller. If the given "suppressions" list is
    not None, checks for expressions formerly warned about are skipped.
    """
    tc_names = get_test_list(run_disabled)
    if not tc_names:
        return (True, "")

    for pat in split_gtest_filter(pat_str):
        expr = re.sub(r"^\-", "", pat)

        if not any(match_name(x, expr) for x in tc_names):
            # Ignore previously reported errors
            if suppressions and expr in suppressions:
                return (False, "")

            # Search for match again, but this time against the full list of tests
            if (not run_disabled and
                    any(match_name(x, expr) for x in test_db.test_case_names)):
                msg = ('Test filter pattern "%s" only matches disabled tests. '
                       'Please enable option "Run disabled tests" for running these.'
                       % expr)
            elif any(expr in x for x in test_db.test_case_names):
                msg = ('Test filter pattern "%s" does not match any test case names. '
                       'Use wildcard "*" for matching on names containing this text.' % expr)
            elif any(match_name_nocase(x, expr) for x in test_db.test_case_names):
                msg = ('Test filter pattern "%s" does not match any test case names. '
                       'Note patterns are case sensitive.' % expr)
            else:
                msg = 'Test filter pattern "%s" does not match any test case names.' % expr

            # Remember reported error
            if suppressions is not None:
                suppressions.append(expr)

            return (False, msg)

    return (True, "")

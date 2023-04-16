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

#
# Library for managing test case filter patterns
#

import re
import sys

import gtest_gui.test_db as test_db
import gtest_gui.tk_utils as tk_utils


class Filter_expr(object):
    def __init__(self, pat_str, opt_run_disabled):
        self.opt_run_disabled = opt_run_disabled
        self.pat_str = pat_str
        self.pat_list = split_gtest_filter(pat_str)
        self.matched_list = None


    def select_test_cases(self, tc_names, enable):
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
        return self.pat_str


    def get_selected_tests(self):
        if self.pat_list:
            if self.matched_list is None:
                self.matched_list = get_matches(self.pat_list, get_test_list(self.opt_run_disabled))
            return self.matched_list
        else:
            return get_test_list(self.opt_run_disabled)


    def can_select_test(self, tc_name):
        if not self.pat_str:
            return True
        else:
            return tc_name not in self.get_selected_tests()


    def can_deselect_test(self, tc_name):
        return self.pat_str and (tc_name in self.get_selected_tests())


    def run_disabled(self):
        return self.opt_run_disabled


# ---------------------------- internal functions ----------------------------


def split_gtest_filter(pat_str):
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
    # TODO convert glob pattern to regexp
    return tk_utils.tk_top.call("string", "match", pat, tc_name)


def match_name_nocase(tc_name, pat):
    return tk_utils.tk_top.call("string", "match", "-nocase", pat, tc_name)


def is_disabled_by_name(tc_name):
    return tc_name.startswith("DISABLED_") or (".DISABLED_" in tc_name)


def build_expr(tc_names, all_tc_names):
    if tc_names:
        tc_excluded = set()
        for tc_name in all_tc_names:
            if not tc_name in tc_names:
                tc_excluded.add(tc_name)

        return build_sub_expr(tc_names, tc_excluded, 0, True)

    else:
        return []


def build_sub_expr(tc_names, tc_excluded, min_prefix_len, allow_neg):
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
    len_1 = sum([len(x) for x in pat_list_1]) + len(pat_list_1)
    len_2 = sum([len(x) for x in pat_list_2]) + len(pat_list_2)
    return len_1 < len_2


def longest_common_prefix(tc_names):
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
    if tc_excluded:
        if len(prefix) <= 1:
            return prefix

        for prefix_len in range(len(prefix) - 1, min_len - 1, -1):
            part = prefix[:prefix_len]
            if any(map(lambda x: x.startswith(part), tc_excluded)):
                return prefix[:prefix_len + 1]

    return prefix[:min_len]


def split_at_prefix(tc_names, prefix_len):
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
    if opt_run_disabled:
        return test_db.test_case_names
    else:
        return [x for x in test_db.test_case_names if not is_disabled_by_name(x)]


def get_test_suite_names(tc_list):
    suites = set()
    for tc_name in tc_list:
        match = re.match(r"^([^\.]+\.)", tc_name)
        if match:
            suites.add(match.group(1))
        else:
            suites.add("")
    return sorted(list(suites))


def get_tests_in_test_suite(tc_suite, all_tc_names):
    if tc_suite:
        return [x for x in all_tc_names if x.startswith(tc_suite)]
    else:
        return [x for x in all_tc_names if "." not in x]


def check_pattern(pat_str, run_disabled, suppressions=None):
    tc_names = get_test_list(run_disabled)
    if not tc_names:
        return (True, "")

    for pat in split_gtest_filter(pat_str):
        expr = re.sub(r"^\-", "", pat)
        is_neg = pat.startswith("-")

        if not any([match_name(x, expr) for x in tc_names]):
            if suppressions is None or not expr in suppressions:
                # Search for match again, but this time against the full list of tests
                if (not run_disabled and
                        any([match_name(x, expr) for x in test_db.test_case_names])):
                    msg = ('Test filter pattern "%s" only matches disabled tests. '
                           'Please enable option "Run disabled tests" for running these.'
                           % expr)
                elif any([expr in x for x in test_db.test_case_names]):
                    msg = ('Test filter pattern "%s" does not match any test case names. '
                           'Use wildcard "*" for matching on names containing this text.' % expr)
                elif any([match_name_nocase(x, expr) for x in test_db.test_case_names]):
                    msg = ('Test filter pattern "%s" does not match any test case names. '
                           'Note patterns are case sensitive.' % expr)
                else:
                    msg = 'Test filter pattern "%s" does not match any test case names.' % expr

                if suppressions is not None:
                    suppressions.append(expr)
                return (False, msg)

            else: # Ignoring due to suppression
                return (False, "")

    return (True, "")

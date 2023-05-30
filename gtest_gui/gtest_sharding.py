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
Implements class GtestSharding
"""

class GtestSharding:
    """
    This class is used for determining an efficient way to schedule test case
    execution with a repetition count larger than 1 using GTest sharding. When
    not using this class, sharing would simply evenly split the test cases into
    sub-sets and assign each sub-set to a different process. This fails to
    speed up test execution when repeating a single test case for a large
    number of times.  If also fails when the number of test cases is small and
    not evently divisble by the number of CPUs. (See CAVEATS section of
    documentation for more details.) Therefore, this class tries to find a way
    to partition the set of test cases by repetitions and GTest sharding so
    that execution time is minimized. For the example of a single test case
    to be repeated many times, it would only partition by repetitions and not
    use sharding at all.

    The class is an iterator. In each iteration it returns parameters for the
    next test job.
    """

    def __init__(self, tc_cnt, rep_cnt, job_cnt, run_all_cnt=0):
        """ Creates an instance of the sharding parameter iterator object. """
        if tc_cnt and rep_cnt and job_cnt:
            (self.__parts, self.__reps) = \
                GtestSharding.__calc_repetitions(
                    GtestSharding.__calc_partitions(tc_cnt, job_cnt - run_all_cnt, rep_cnt),
                    tc_cnt, rep_cnt)

            if run_all_cnt:
                self.__parts.extend([1] * run_all_cnt)
                self.__reps.extend([rep_cnt] * run_all_cnt)

        else:
            self.__parts = [job_cnt]
            self.__reps = [rep_cnt]

        self.__cur_part_idx = 0
        self.__cur_shard_idx = -1


    def __iter__(self):
        self.__cur_part_idx = 0
        self.__cur_shard_idx = -1
        return self


    def __next__(self):
        self.__cur_shard_idx += 1
        if self.__cur_shard_idx >= self.__parts[self.__cur_part_idx]:
            self.__cur_part_idx += 1
            self.__cur_shard_idx = 0
        if self.__cur_part_idx < len(self.__parts):
            return (self.__reps[self.__cur_part_idx],
                    self.__parts[self.__cur_part_idx],
                    self.__cur_shard_idx)

        raise StopIteration


    def next(self):
        """
        Returns sharding parameters for the next test process.
        """
        return self.__next__()


    @staticmethod
    def get_tc_count_per_shard(tc_cnt, rep_cnt, shard_size, shard_idx):
        """
        Calculates the number of test case results expected for a test process
        with the given sharding parameters. This is basically the number of test
        cases divided by the number of CPUs, but with consideration of the case
        that the test case number isn't divisible by the number of CPUs.
        """
        div = tc_cnt // shard_size
        rem = tc_cnt % shard_size
        return rep_cnt * (div if shard_idx >= rem else div + 1)


    @staticmethod
    def __calc_repetitions(partitions, tc_cnt, rep_cnt):
        min_time = tc_cnt * rep_cnt
        min_parts = None
        min_reps = None
        for part in partitions:
            tcs = [int((tc_cnt + x - 1) / x) for x in part]

            # step #1: estimate repetiton count based on TC# relation between CPU partitions
            # (needed for reducing the number of iterations in step 2)
            tc_est = [tcs[0] / x for x in tcs]
            sum_est = sum(tc_est)
            reps = [int(rep_cnt / sum_est * x) for x in tc_est]
            tcs_rep = tcs.copy()
            # pylint: disable=consider-using-enumerate
            for rep_idx in range(len(tcs_rep)):
                tcs_rep[rep_idx] *= reps[rep_idx]

            # step #2: distribute remaining repetitions to partitions
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


    @staticmethod
    def __calc_partitions(tc_cnt, job_cnt, rep_cnt):
        # Start recursion for enumeration of possible partitionings
        partitions = GtestSharding.__calc_parts_sub([], job_cnt, tc_cnt, rep_cnt, job_cnt)
        return partitions


    @staticmethod
    def __calc_parts_sub(pre_part, cpu_cnt, tc_cnt, rep_cnt, max_cpu_cnt):
        #print("DBG %s | %d,%d,%d,%d" % (str(pre_part), cpu_cnt, tc_cnt, rep_cnt, max_cpu_cnt))
        partitions = []
        prev_cval = 0
        div = 1
        while True:
            cval = int((tc_cnt + div - 1) / div)

            if cval != prev_cval and cval <= max_cpu_cnt:
                if cval > 1:
                    cnt = int(cpu_cnt / cval)
                    part = pre_part + ([cval] * cnt)
                    remainder = cpu_cnt - (cval * cnt)

                    if remainder > 0:
                        # Recurse to decide partitioning of remaining CPUs
                        partitions.extend(GtestSharding.__calc_parts_sub(part, remainder,
                                                                         tc_cnt, rep_cnt,
                                                                         min(remainder, cval)))
                    else:
                        partitions.append(part)
                else:
                    partitions.append(pre_part + [1] * cpu_cnt)

            prev_cval = cval
            if cval <= 1:
                break
            div += 1

        if not partitions:
            partitions.append(pre_part + [cpu_cnt])

        return partitions

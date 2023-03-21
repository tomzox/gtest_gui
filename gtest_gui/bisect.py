#!/usr/bin/env python3
#
# Source: https://github.com/python/cpython/blob/3.11/Lib/bisect.py
#
# Replacement for Python's bisect_left in Python versions before 3.10,
# which did not support the "key" parameter yet.

#import sys
#if sys.version_info[0] >= 3 and sys.version_info[0] >= 10:
#    import bisect
#    def bisect_left(lst, value, keyfn):
#        return bisect.bisect_left(lst, value, key=keyfn)
#else:

def bisect_left(lst, value, keyfn):
    value_key = keyfn(value)
    lo = 0
    hi = len(lst)
    while lo < hi:
        mid = (lo + hi) // 2
        if keyfn(lst[mid]) < value_key:
            lo = mid + 1
        else:
            hi = mid
    return lo

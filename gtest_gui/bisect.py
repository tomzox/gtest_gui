#!/usr/bin/env python3
#
# Source: https://github.com/python/cpython/blob/3.11/Lib/bisect.py

""" Defines a replacement for Python's bisect_left that supports the "key" parameter. """

def bisect_left(lst, value, keyfn):
    """
    Replacement for Python's bisect_left, which did not support the "key"
    parameter in Python versions before 3.10. This code is copied from the
    Python 3.11 library, but with a minor simplification as the "keyfn"
    parameter is made mandatory.
    """
    value_key = keyfn(value)
    low = 0
    high = len(lst)
    while low < high:
        mid = (low + high) // 2
        if keyfn(lst[mid]) < value_key:
            low = mid + 1
        else:
            high = mid
    return low

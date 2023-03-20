#!/usr/bin/env python3

import os
import subprocess
import sys

if sys.platform == "win32":
    # Posted to stackoverflow.com by anatoly techtonik, Dec/29/2015

    from ctypes import windll, byref, wintypes, GetLastError, WinError, POINTER
    from ctypes.wintypes import HANDLE, DWORD, BOOL
    import msvcrt


    LPDWORD = POINTER(DWORD)
    PIPE_NOWAIT = wintypes.DWORD(0x00000001)
    ERROR_NO_DATA = 232


    def subprocess_creationflags():
        return subprocess.CREATE_NO_WINDOW


    def set_nonblocking(pipe):
        SetNamedPipeHandleState = windll.kernel32.SetNamedPipeHandleState
        SetNamedPipeHandleState.argtypes = [HANDLE, LPDWORD, LPDWORD, LPDWORD]
        SetNamedPipeHandleState.restype = BOOL

        handle = msvcrt.get_osfhandle(pipe.fileno())

        res = windll.kernel32.SetNamedPipeHandleState(handle, byref(PIPE_NOWAIT), None, None)
        if res == 0:
            raise OSError(GetLastError(), WinError())


    def read_nonblocking(pipe, length):
        try:
            return os.read(pipe.fileno(), length)
        except OSError as e:
            if GetLastError() != ERROR_NO_DATA:
                raise OSError(GetLastError(), WinError())
            return None


else:
    import fcntl


    def subprocess_creationflags():
        return 0


    def set_nonblocking(pipe):
        flags = fcntl.fcntl(pipe, fcntl.F_GETFL)
        fcntl.fcntl(pipe, fcntl.F_SETFL, flags | os.O_NONBLOCK)


    def read_nonblocking(pipe, length):
        #try:
        #    return os.read(pipe.fileno(), length)
        #except BlockingIOError:
        #    data = None
        return pipe.read(length)

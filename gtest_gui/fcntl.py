#!/usr/bin/env python3

""" Helper functions for non-blocking operation of pipes. """

import os
import subprocess
import sys

if sys.platform == "win32":
    # Posted to stackoverflow.com by anatoly techtonik, Dec/29/2015

    from ctypes import windll, byref, wintypes, GetLastError, WinError, POINTER
    from ctypes.wintypes import HANDLE, DWORD, BOOL
    # pylint tries to check this code even when run on POSIX platform
    # pylint: disable=import-error
    import msvcrt


    LPDWORD = POINTER(DWORD)
    PIPE_NOWAIT = wintypes.DWORD(0x00000001)
    ERROR_NO_DATA = 232


    def subprocess_creationflags():
        """
        Returns additional platform-specific flags needed to pass to subprocess
        creation to suppress opening of a "console window".
        """
        return subprocess.CREATE_NO_WINDOW


    def set_nonblocking(pipe):
        """
        Configure the given pipe handle to be non-blocking when reading from
        it, equivalently to O_NONBLOCK on POSIX platform.
        """
        SetNamedPipeHandleState = windll.kernel32.SetNamedPipeHandleState
        SetNamedPipeHandleState.argtypes = [HANDLE, LPDWORD, LPDWORD, LPDWORD]
        SetNamedPipeHandleState.restype = BOOL

        handle = msvcrt.get_osfhandle(pipe.fileno())

        res = windll.kernel32.SetNamedPipeHandleState(handle, byref(PIPE_NOWAIT), None, None)
        if res == 0:
            raise OSError(GetLastError(), WinError())


    def read_nonblocking(pipe, length):
        """
        Read from a non-blocking pipe. If there is no data return None. Any
        other errors raise exception OSError.
        """
        try:
            return os.read(pipe.fileno(), length)
        except OSError:
            if GetLastError() != ERROR_NO_DATA:
                raise OSError(GetLastError(), WinError())
            return None


else:
    import fcntl


    def subprocess_creationflags():
        """
        Returns additional platform-specific flags needed to pass to subprocess
        creation. On POSIX platforms this function is not needed and returns 0.
        """
        return 0


    def set_nonblocking(pipe):
        """
        Configure the given file descriptor to be non-blocking for read/write.
        """
        flags = fcntl.fcntl(pipe, fcntl.F_GETFL)
        fcntl.fcntl(pipe, fcntl.F_SETFL, flags | os.O_NONBLOCK)


    def read_nonblocking(pipe, length):
        """
        Read from a non-blocking pipe. Returns an empty string if there is no data.
        """
        #try:
        #    return os.read(pipe.fileno(), length)
        #except BlockingIOError:
        #    data = None
        return pipe.read(length)

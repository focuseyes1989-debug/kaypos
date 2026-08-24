"""Windows single-instance guard for desktop entry points."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


ERROR_ALREADY_EXISTS = 183
ERROR_ACCESS_DENIED = 5
SYNCHRONIZE = 0x00100000


class SingleInstanceGuard:
    """Keep a named Windows mutex alive for the lifetime of this object."""

    def __init__(self, name: str):
        self.name = name
        self._handle = None

    def acquire(self) -> bool:
        """Return ``False`` when another process already owns this app mutex."""
        if os.name != "nt":
            return True

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        kernel32.CreateMutexW.restype = wintypes.HANDLE

        ctypes.set_last_error(0)
        handle = kernel32.CreateMutexW(None, False, self.name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())

        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False

        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle is None or os.name != "nt":
            return
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(self._handle)
        self._handle = None

    def __del__(self):
        self.release()


def is_single_instance_running(name: str) -> bool:
    """Check a named mutex without acquiring or changing its ownership."""
    if os.name != "nt":
        return False

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenMutexW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.OpenMutexW.restype = wintypes.HANDLE
    ctypes.set_last_error(0)
    handle = kernel32.OpenMutexW(SYNCHRONIZE, False, name)
    if handle:
        kernel32.CloseHandle(handle)
        return True
    # A mutex in another Windows session may exist but deny this process access.
    return ctypes.get_last_error() == ERROR_ACCESS_DENIED


def show_already_running_message(
    title: str = "KAY POS",
    message: str = "KAY POS is already running on this computer.",
) -> None:
    """Show a native dialog without constructing a second QApplication."""
    if os.name == "nt":
        # MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x00000040 | 0x00010000)
    else:
        print(message)

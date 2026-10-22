"""Immediate Windows Unicode clipboard transfer, invoked only by Copy."""
import ctypes
from ctypes import wintypes
import time


def copy_text(owner, text):
    """Set and check CF_UNICODETEXT without delayed Tk clipboard rendering.

    Contents stay in this local process/Windows clipboard. Never log them.
    Windows owns the allocated memory after successful SetClipboardData.
    """
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL
    blob = text.encode("utf-16-le") + b"\0\0"
    handle = kernel32.GlobalAlloc(0x0002, len(blob))
    if not handle:
        raise OSError("Clipboard allocation failed")
    opened, transferred = False, False
    try:
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            raise OSError("Clipboard allocation lock failed")
        try:
            ctypes.memmove(pointer, blob, len(blob))
        finally:
            kernel32.GlobalUnlock(handle)
        for _ in range(10):
            if user32.OpenClipboard(owner):
                opened = True
                break
            time.sleep(.03)
        if not opened:
            raise OSError("Clipboard is busy")
        if not user32.EmptyClipboard() or not user32.SetClipboardData(13, handle):
            raise OSError("Clipboard write failed")
        transferred = True
        read_handle = user32.GetClipboardData(13)
        pointer = kernel32.GlobalLock(read_handle) if read_handle else None
        if not pointer:
            raise OSError("Clipboard readback failed")
        try:
            if ctypes.wstring_at(pointer, len(text)) != text:
                raise OSError("Clipboard verification failed")
        finally:
            kernel32.GlobalUnlock(read_handle)
    finally:
        if opened:
            user32.CloseClipboard()
        if not transferred:
            kernel32.GlobalFree(handle)

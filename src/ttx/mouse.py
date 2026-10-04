"""Shared terminal mouse setup and single-action button decoding."""
import curses
import os
import sys

_console_mouse = None


def _windows_motion(enable):
    """Enable unbuttoned console mouse reports and suppress Quick Edit selection."""
    global _console_mouse
    if os.name != "nt" or not sys.stdin.isatty():
        return
    try:
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetStdHandle.argtypes = [wintypes.DWORD]
        kernel.GetStdHandle.restype = wintypes.HANDLE
        kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        if not enable:
            if _console_mouse:
                kernel.SetConsoleMode(*_console_mouse)
                _console_mouse = None
            return
        handle = kernel.GetStdHandle(-10)  # STD_INPUT_HANDLE
        mode = wintypes.DWORD()
        if kernel.GetConsoleMode(handle, ctypes.byref(mode)):
            if _console_mouse is None:
                _console_mouse = handle, mode.value
            kernel.SetConsoleMode(handle, (mode.value | 0x0010 | 0x0080) & ~0x0040)
    except (AttributeError, OSError):
        pass


def enable_mouse():
    try:
        curses.mouseinterval(0)
    except curses.error:
        pass  # Some terminal backends do not expose click timing.
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    _windows_motion(True)
    # ncurses requests drag reports; 1003 also reports motion with no button.
    if os.name != "nt" and sys.stdout.isatty():
        sys.stdout.write("\033[?1003h")
        sys.stdout.flush()


def disable_mouse():
    curses.mousemask(0)
    _windows_motion(False)
    if os.name != "nt" and sys.stdout.isatty():
        sys.stdout.write("\033[?1003l")
        sys.stdout.flush()


def button(state, number=1):
    return bool(state & (getattr(curses, f"BUTTON{number}_PRESSED", 0) |
                         getattr(curses, f"BUTTON{number}_CLICKED", 0)))


def wheel(state):
    if state & getattr(curses, "BUTTON4_PRESSED", 0):
        return -1
    if state & getattr(curses, "BUTTON5_PRESSED", 0):
        return 1
    return 0

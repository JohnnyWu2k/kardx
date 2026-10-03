"""Continuous controls with native Windows releases and a repeat fallback."""

from __future__ import annotations

import ctypes
import os
import sys
import time

REPEAT_LEASE = 0.18
TAP_DURATION = 0.07


def terminal_window(user32, kernel32):
    """Find this console's visible owner, without guessing from foreground focus."""
    kernel32.GetConsoleWindow.argtypes = []
    kernel32.GetConsoleWindow.restype = ctypes.c_void_p
    user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    user32.GetAncestor.restype = ctypes.c_void_p
    user32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar), ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    console = kernel32.GetConsoleWindow()
    if not console:
        return None
    window = user32.GetAncestor(console, 3)  # GA_ROOTOWNER follows parents and owners.
    if not window:
        return None
    class_name = ctypes.create_unicode_buffer(256)
    if not user32.GetClassNameW(window, class_name, len(class_name)):
        return None
    if class_name.value not in ("ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS"):
        return None
    return window


def windows_key_state():
    if os.name != "nt" or not sys.stdin.isatty():
        return None
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short
        window = terminal_window(user32, kernel32)
        if not window:
            return None

        def focused():
            return user32.GetForegroundWindow() == window

        def sample():
            if not focused():
                sample.movement_down = False
                return 0, False
            down = lambda key: bool(user32.GetAsyncKeyState(key) & 0x8000)
            left = down(0x41) or down(0x25)
            right = down(0x44) or down(0x27)
            sample.movement_down = left or right
            return int(right) - int(left), down(0x57) or down(0x26) or down(0x20)

        sample.focused = focused
        sample.movement_down = False
        return sample
    except (AttributeError, OSError):
        return None


class MotionInput:
    def __init__(self, key_state=None):
        self.key_state = key_state
        self.reset()

    def reset(self):
        self.direction = 0
        self.expires = 0.0
        self.jump_pending = False
        # Changing input owners (menu/build/battle) must not turn an already
        # held jump key into a fresh jump when exploration resumes.
        self.jump_down = bool(self.key_state()[1]) if self.key_state else False
        self.jump_expires = 0.0
        self.native_direction = 0
        self.tap_direction = 0
        self.tap_until = 0.0
        self.tap_pending = False

    def feed(self, key: str, now: float | None = None):
        now = time.monotonic() if now is None else now
        if key in ("a", "d"):
            self.direction = -1 if key == "a" else 1
            self.expires = now + REPEAT_LEASE
            self.tap_pending = True
        elif key in ("w", " "):
            if self.key_state and not self.jump_down or not self.key_state and now >= self.jump_expires:
                self.jump_pending = True
            self.jump_expires = now + REPEAT_LEASE

    def sample(self, now: float | None = None) -> tuple[int, bool]:
        now = time.monotonic() if now is None else now
        if self.key_state:
            if not getattr(self.key_state, "focused", lambda: True)():
                self.reset()
                return 0, False
            direction, held_jump = self.key_state()
            if direction or self.native_direction or getattr(self.key_state, "movement_down", False):
                # Physical release wins over buffered auto-repeat events.
                self.tap_direction = 0
                self.tap_until = 0.0
            elif self.tap_pending and now < self.expires:
                # A tap can begin and end between native polls. Give its
                # terminal event a small impulse instead of losing it.
                self.tap_direction = self.direction
                self.tap_until = now + TAP_DURATION
            self.tap_pending = False
            self.native_direction = direction
            if not direction and now < self.tap_until:
                direction = self.tap_direction
            pressed_jump = self.jump_pending or held_jump and not self.jump_down
            self.jump_pending = False
            self.jump_down = held_jump
            return direction, pressed_jump
        direction = self.direction if now < self.expires else 0
        jump = self.jump_pending
        self.jump_pending = False
        return direction, jump

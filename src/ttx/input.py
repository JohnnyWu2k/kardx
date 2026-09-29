"""Continuous controls with native Windows releases and a repeat fallback."""

from __future__ import annotations

import ctypes
import os
import sys
import time

REPEAT_LEASE = 0.18


def windows_key_state():
    if os.name != "nt" or not sys.stdin.isatty():
        return None
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short
        foreground = user32.GetForegroundWindow()

        def sample():
            if not foreground or user32.GetForegroundWindow() != foreground:
                return 0, False
            down = lambda key: bool(user32.GetAsyncKeyState(key) & 0x8000)
            left = down(0x41) or down(0x25)
            right = down(0x44) or down(0x27)
            return int(right) - int(left), down(0x57) or down(0x26) or down(0x20)

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

    def feed(self, key: str, now: float | None = None):
        now = time.monotonic() if now is None else now
        if key in ("a", "d"):
            self.direction = -1 if key == "a" else 1
            self.expires = now + REPEAT_LEASE
        elif key in ("w", " "):
            if self.key_state and not self.jump_down or not self.key_state and now >= self.jump_expires:
                self.jump_pending = True
            self.jump_expires = now + REPEAT_LEASE

    def sample(self, now: float | None = None) -> tuple[int, bool]:
        now = time.monotonic() if now is None else now
        if self.key_state:
            direction, held_jump = self.key_state()
            pressed_jump = self.jump_pending or held_jump and not self.jump_down
            self.jump_pending = False
            self.jump_down = held_jump
            return direction, pressed_jump
        direction = self.direction if now < self.expires else 0
        jump = self.jump_pending
        self.jump_pending = False
        return direction, jump

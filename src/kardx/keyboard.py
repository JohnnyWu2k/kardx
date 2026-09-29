# src/keyboard.py
# A simple, cross-platform module for single-key presses.
import sys
from contextlib import contextmanager
from contextvars import ContextVar

_key_readers = ContextVar("kardx_key_readers", default=None)


@contextmanager
def use_key_reader(blocking, non_blocking):
    token = _key_readers.set((blocking, non_blocking))
    try:
        yield
    finally:
        _key_readers.reset(token)

KEY_UP = b'<UP>'
KEY_DOWN = b'<DOWN>'
KEY_LEFT = b'<LEFT>'
KEY_RIGHT = b'<RIGHT>'
KEY_ENTER = b'<ENTER>'
KEY_ESC = b'<ESC>'
KEY_Q = b'q'
KEY_E = b'e'
KEY_D = b'd'


def _normalize_key(key: bytes) -> bytes:
    if key in (b'\r', b'\n'):
        return KEY_ENTER
    if key == b'\x1b':
        return KEY_ESC
    if len(key) == 1 and b'A' <= key <= b'Z':
        return key.lower()
    return key


def _special_key_from_scan_code(key: bytes) -> bytes:
    return {
        b'H': KEY_UP,
        b'P': KEY_DOWN,
        b'K': KEY_LEFT,
        b'M': KEY_RIGHT,
    }.get(key, key)


try:
    # --- Windows Implementation ---
    import msvcrt
    def _get_key():
        """Gets a single key press (blocking)."""
        key = msvcrt.getch()
        if key in b'\x00\xe0': # Special key prefix
            return _special_key_from_scan_code(msvcrt.getch())
        return _normalize_key(key)

    def _get_key_non_blocking():
        """Gets a single key press if one is available (non-blocking)."""
        if msvcrt.kbhit():
            return _get_key() # Reuse the blocking logic to handle special keys
        return None

except ImportError:
    # --- Unix-like Systems Implementation (Linux, macOS) ---
    import tty
    import termios
    import select

    def _read_unix_escape_sequence(fd) -> bytes:
        if select.select([sys.stdin], [], [], 0.02) != ([sys.stdin], [], []):
            return KEY_ESC
        first = sys.stdin.read(1)
        if first != '[':
            return KEY_ESC
        if select.select([sys.stdin], [], [], 0.02) != ([sys.stdin], [], []):
            return KEY_ESC
        second = sys.stdin.read(1)
        if second == 'A':
            return KEY_UP
        if second == 'B':
            return KEY_DOWN
        if second == 'C':
            return KEY_RIGHT
        if second == 'D':
            return KEY_LEFT
        return KEY_ESC
    
    def _get_key():
        """Gets a single key press (blocking)."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            key = sys.stdin.read(1)
            if key == '\x1b': # Arrow key prefix
                return _read_unix_escape_sequence(fd)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return _normalize_key(key.encode('utf-8'))

    def _get_key_non_blocking():
        """Gets a single key press if one is available (non-blocking)."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            # Check if there is data to be read
            if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                # This part is tricky for multi-byte arrow keys in non-blocking mode.
                key = sys.stdin.read(1)
                if key == '\x1b':
                    return _read_unix_escape_sequence(fd)
                return _normalize_key(key.encode('utf-8'))
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return None


def get_key():
    readers = _key_readers.get()
    return readers[0]() if readers else _get_key()


def get_key_non_blocking():
    readers = _key_readers.get()
    return readers[1]() if readers else _get_key_non_blocking()

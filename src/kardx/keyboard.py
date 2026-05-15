# src/keyboard.py
# A simple, cross-platform module for single-key presses.
import sys

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
    def get_key():
        """Gets a single key press (blocking)."""
        key = msvcrt.getch()
        if key in b'\x00\xe0': # Special key prefix
            return _special_key_from_scan_code(msvcrt.getch())
        return _normalize_key(key)

    def get_key_non_blocking():
        """Gets a single key press if one is available (non-blocking)."""
        if msvcrt.kbhit():
            return get_key() # Reuse the blocking logic to handle special keys
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
    
    def get_key():
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

    def get_key_non_blocking():
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

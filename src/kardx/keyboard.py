# src/keyboard.py
# A simple, cross-platform module for single-key presses.
import sys

try:
    # --- Windows Implementation ---
    import msvcrt
    def get_key():
        """Gets a single key press (blocking)."""
        key = msvcrt.getch()
        if key in b'\x00\xe0': # Special key prefix
            return msvcrt.getch()
        return key

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
    
    def get_key():
        """Gets a single key press (blocking)."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            key = sys.stdin.read(1)
            if key == '\x1b': # Arrow key prefix
                seq = sys.stdin.read(2)
                if seq == '[A': return b'H' # Up
                if seq == '[B': return b'P' # Down
                if seq == '[C': return b'M' # Right
                if seq == '[D': return b'K' # Left
                return seq
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return key.encode('utf-8')

    def get_key_non_blocking():
        """Gets a single key press if one is available (non-blocking)."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            # Check if there is data to be read
            if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                # This part is tricky for multi-byte arrow keys in non-blocking mode.
                # For simplicity, we'll read one char, which works for regular keys.
                # A full solution would require a more complex state machine.
                return sys.stdin.read(1).encode('utf-8')
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return None


# --- Key Constants (no changes) ---
KEY_UP = b'H'
KEY_DOWN = b'P'
KEY_LEFT = b'K'
KEY_RIGHT = b'M'
KEY_ENTER = b'\r'
KEY_ESC = b'\x1b'
KEY_Q = b'q'
KEY_E = b'e'
KEY_D = b'd'
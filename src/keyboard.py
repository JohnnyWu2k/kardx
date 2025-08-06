# src/keyboard.py
# A simple, cross-platform module for single-key presses.

try:
    # For Windows
    import msvcrt
    def get_key():
        """Gets a single key press on Windows."""
        # This will catch regular keys and the first byte of special keys
        key = msvcrt.getch()
        # If it's a special key (like arrows), it sends two bytes.
        # We check if there's more in the buffer to detect them.
        if key in b'\x00\xe0': # Special key prefix
            # The second byte identifies the key (e.g., H for Up Arrow)
            special_key = msvcrt.getch()
            return special_key
        return key

except ImportError:
    # For Unix-like systems (Linux, macOS)
    import sys
    import tty
    import termios
    def get_key():
        """Gets a single key press on Unix-like systems."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            # Read just one byte. Special keys are sent as sequences.
            key = sys.stdin.read(1)
            # Arrow keys are sent as '\x1b[A' (Up), '\x1b[B' (Down), etc.
            # We check for the escape sequence prefix.
            if key == '\x1b':
                # Read the next two characters of the sequence
                seq = sys.stdin.read(2)
                if seq == '[A': return b'H' # Up Arrow
                if seq == '[B': return b'K' # Down Arrow
                if seq == '[C': return b'M' # Right Arrow
                if seq == '[D': return b'P' # Left Arrow
                return seq # Other escape sequences
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return key.encode('utf-8') # Return as bytes for consistency

# --- Key Constants ---
# We use the bytes returned by Windows msvcrt for consistency.
# Use these constants in the controller instead of raw characters.
KEY_UP = b'H'
KEY_DOWN = b'P' # Note: 'P' is often Down on Windows
KEY_LEFT = b'K'
KEY_RIGHT = b'M'
KEY_ENTER = b'\r'
KEY_ESC = b'\x1b'
KEY_Q = b'q'
KEY_E = b'e'
KEY_D = b'd'
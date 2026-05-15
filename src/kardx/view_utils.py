# src/view_utils.py
import os
import re
import subprocess
import sys
from shutil import get_terminal_size
from wcwidth import wcwidth, wcswidth
from .settings import settings_manager
from .loader import ensure_editable_data_file


def open_file(filename: str):
    """
    Opens a file in the data directory with the default system application.
    This provides a cross-platform way to easily edit game data.
    """
    try:
        file_path = ensure_editable_data_file(filename)
        print(f"\nOpening editable data file: {file_path}")
        print("The game loads this user copy on the next restart.")

        if sys.platform == "win32":
            os.startfile(file_path)
        elif sys.platform == "darwin":
            subprocess.call(['open', file_path])
        else:
            subprocess.call(['xdg-open', file_path])
    except (FileNotFoundError, AttributeError):
        print(f"Error: Could not find the data file '{filename}' inside the package.")
    except Exception as e:
        print(f"Error: Failed to open file. Your system may not have a default editor for '.jsonc' files.")
        print(f"Details: {e}")

def terminal_size() -> tuple[int, int]:
    size = get_terminal_size(fallback=(80, 24))
    return max(40, size.columns), max(16, size.lines)


def clear_screen():
    sys.stdout.write("\033[?25l\033[H\033[J")
    sys.stdout.flush()


def render_screen(lines: list[str]):
    term_width, term_height = terminal_size()
    visible_lines = []
    for line in lines[:term_height]:
        fitted = fit_to_width(line, term_width)
        padding = " " * max(0, term_width - get_visible_len(fitted))
        visible_lines.append(fitted + padding)
    output = "\n".join(visible_lines)
    sys.stdout.write("\033[?25l\033[H\033[J" + output)
    sys.stdout.flush()


def show_cursor():
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()

def get_visible_len(s: str) -> int:
    return wcswidth(re.sub(r'\033\[[0-9;]*m', '', s))


def fit_to_width(text: str, width: int) -> str:
    visible_width = 0
    output = []
    index = 0
    while index < len(text) and visible_width < width:
        if text[index] == "\033":
            match = re.match(r'\033\[[0-9;]*m', text[index:])
            if match:
                output.append(match.group(0))
                index += len(match.group(0))
                continue
        char_width = max(0, wcwidth(text[index]))
        if visible_width + char_width > width:
            break
        output.append(text[index])
        visible_width += char_width
        index += 1
    return "".join(output)

class Colors:
    """A utility class for dynamically applying themed colors based on settings."""
    _ENDC = '\033[0m'

    THEMES = {
        "default": {
            "accent": '\033[92m',  # Green
            "positive": '\033[92m', # Green
            "negative": '\033[91m',  # Red
            "neutral": '\033[94m',   # Blue
            "white": '\033[97m',
        },
        "ocean": {
            "accent": '\033[96m',  # Cyan
            "positive": '\033[92m', # Green
            "negative": '\033[93m',  # Yellow
            "neutral": '\033[94m',   # Blue
            "white": '\033[97m',
        },
        "forest": {
            "accent": '\033[93m',  # Yellow
            "positive": '\033[92m', # Green
            "negative": '\033[91m',  # Red
            "neutral": '\033[33m',   # Dark Yellow/Brown
            "white": '\033[97m',
        }
    }

    @staticmethod
    def _colorize(color_name: str, text: str) -> str:
        """Applies a themed color to text if colors are enabled."""
        if not settings_manager.get("enable_colors", True):
            return text
        
        theme_name = settings_manager.get("color_theme", "default")
        active_theme = Colors.THEMES.get(theme_name, Colors.THEMES["default"])
        color_code = active_theme.get(color_name, "")
        
        return f"{color_code}{text}{Colors._ENDC}"

    # --- Semantic Color Methods ---
    @staticmethod
    def accent(text: str) -> str: return Colors._colorize("accent", text)
    @staticmethod
    def positive(text: str) -> str: return Colors._colorize("positive", text)
    @staticmethod
    def negative(text: str) -> str: return Colors._colorize("negative", text)
    @staticmethod
    def neutral(text: str) -> str: return Colors._colorize("neutral", text)
    @staticmethod
    def white(text: str) -> str: return Colors._colorize("white", text)

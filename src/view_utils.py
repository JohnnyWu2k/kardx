# src/view_utils.py
import os
import re
import subprocess
import sys
from wcwidth import wcswidth
from .settings import settings_manager


def open_file(filename: str):
    """
    Opens a file in the data directory with the default system application.
    This provides a cross-platform way to easily edit game data.
    """
    # We must use importlib.resources to get a real, temporary path to the file
    # that exists on the filesystem, especially when the app is packaged.
    from importlib import resources
    try:
        # 'with' statement ensures the temporary file is cleaned up
        with resources.as_file(resources.files("src.data").joinpath(filename)) as file_path:
            print(f"\nAttempting to open '{filename}' with your default editor...")
            
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin": # macOS
                subprocess.call(['open', file_path])
            else: # Linux and other Unix-like
                subprocess.call(['xdg-open', file_path])
    except (FileNotFoundError, AttributeError):
        print(f"Error: Could not find the data file '{filename}' inside the package.")
    except Exception as e:
        print(f"Error: Failed to open file. Your system may not have a default editor for '.jsonc' files.")
        print(f"Details: {e}")

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_visible_len(s: str) -> int:
    return wcswidth(re.sub(r'\033\[[0-9;]*m', '', s))

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
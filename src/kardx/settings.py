import json5
import os
from pathlib import Path
from .loader import load_packaged_json5_data

class Settings:
    """Manages loading, accessing, and saving game settings."""
    def __init__(self, settings_path: Path):
        self.path = settings_path
        self.data = self._load_defaults()
        self.load()

    def _load_defaults(self) -> dict:
        """Returns the default settings in case the file is missing."""
        packaged_defaults = load_packaged_json5_data("settings.jsonc")
        if isinstance(packaged_defaults, dict):
            return packaged_defaults
        return {
            "show_enemy_hand": True,
            "enable_colors": True,
            "enable_menu_animations": True,
            "animation_speed_multiplier": 1.0,
            "color_theme": "default",
        }

    def load(self):
        """Loads settings from the JSONC file."""
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                user_settings = json5.load(f)
                self.data.update(user_settings)
        except FileNotFoundError:
            self._save_with_fallback()
        except Exception:
            self._save_with_fallback()

    def _save_with_fallback(self):
        try:
            self.save()
        except OSError:
            self.path = Path.cwd() / ".kardx" / "settings.jsonc"
            self.save()

    def save(self):
        """Saves the current settings to the JSONC file in a strict, compatible format."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            f.write(json5.dumps(
                self.data, 
                indent=2, 
                quote_keys=True,
                trailing_commas=False
            ))

    def get(self, key: str, default=None):
        """Gets a setting value by key."""
        return self.data.get(key, default)

    def set(self, key: str, value):
        """Sets a setting value and saves it."""
        self.data[key] = value
        self._save_with_fallback()


def _default_settings_file() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "Kard-X" / "settings.jsonc"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "kardx" / "settings.jsonc"


SETTINGS_FILE = _default_settings_file()
settings_manager = Settings(SETTINGS_FILE)

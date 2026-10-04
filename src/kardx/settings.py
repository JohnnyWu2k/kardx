import json5
import math
import os
from pathlib import Path
from .loader import load_packaged_json5_data
from .persistence import atomic_write_text

class Settings:
    """Manages loading, accessing, and saving game settings."""
    def __init__(self, settings_path: Path):
        self.path = settings_path
        self.data = self._load_defaults()
        self.load()

    def _load_defaults(self) -> dict:
        """Returns the default settings in case the file is missing."""
        defaults = {
            "show_enemy_hand": True,
            "enable_colors": True,
            "enable_menu_animations": True,
            "animation_speed_multiplier": 1.0,
            "color_theme": "default",
            "battle_particle_color": "magenta",
            "battle_particle_speed": 1.0,
            "battle_transition_duration": 0.6,
        }
        packaged_defaults = load_packaged_json5_data("settings.jsonc")
        return self._validated(packaged_defaults, defaults) if isinstance(packaged_defaults, dict) else defaults

    def load(self):
        """Loads settings from the JSONC file."""
        defaults = self._load_defaults()
        self.data = dict(defaults)
        paths = [self.path]
        if self.path == _default_settings_file():
            paths.insert(0, Path.cwd() / ".kardx" / "settings.jsonc")
        for path in paths:
            try:
                with path.open('r', encoding='utf-8') as stream:
                    user_settings = json5.load(stream)
            except (OSError, ValueError):
                continue
            if isinstance(user_settings, dict):
                self.data = self._validated(user_settings, defaults)
                self.path = path
                return
        # Reading defaults must not create files or overwrite a malformed copy.

    @staticmethod
    def _validated(values: dict, defaults: dict) -> dict:
        data = {**defaults, **values}
        for key in ("show_enemy_hand", "enable_colors", "enable_menu_animations"):
            if type(data.get(key)) is not bool:
                data[key] = defaults[key]
        speed = data.get("animation_speed_multiplier")
        if type(speed) not in (int, float) or type(speed) is float and not math.isfinite(speed):
            speed = defaults["animation_speed_multiplier"]
        data["animation_speed_multiplier"] = float(max(0.1, min(2.0, speed)))
        if data.get("color_theme") not in ("default", "ocean", "forest"):
            data["color_theme"] = defaults["color_theme"]
        if data.get("battle_particle_color") not in ("magenta", "cyan", "blue", "green", "gold", "red", "white"):
            data["battle_particle_color"] = "magenta"
        for key, low, high, fallback in (("battle_particle_speed", 0.25, 4.0, 1.0),
                                         ("battle_transition_duration", 0.0, 3.0, 0.6)):
            value = data.get(key, fallback)
            if type(value) not in (int, float) or not math.isfinite(value):
                value = fallback
            data[key] = max(low, min(high, float(value)))
        return data

    def _save_with_fallback(self):
        try:
            self.save()
        except OSError:
            self.path = Path.cwd() / ".kardx" / "settings.jsonc"
            self.save()

    def save(self):
        """Saves the current settings to the JSONC file in a strict, compatible format."""
        atomic_write_text(self.path, json5.dumps(
            self.data,
            indent=2,
            quote_keys=True,
            trailing_commas=False,
        ))

    def get(self, key: str, default=None):
        """Gets a setting value by key."""
        return self.data.get(key, default)

    def set(self, key: str, value):
        """Sets a setting value and saves it."""
        self.data = self._validated({**self.data, key: value}, self._load_defaults())
        self._save_with_fallback()


def _default_settings_file() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "Kard-X" / "settings.jsonc"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "kardx" / "settings.jsonc"


SETTINGS_FILE = _default_settings_file()
settings_manager = Settings(SETTINGS_FILE)

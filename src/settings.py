# src/settings.py
import json5
from pathlib import Path

class Settings:
    """Manages loading, accessing, and saving game settings."""
    def __init__(self, settings_path: Path):
        self.path = settings_path
        self.data = self._load_defaults()
        self.load()

    def _load_defaults(self) -> dict:
        """Returns the default settings in case the file is missing."""
        return {
            "show_enemy_hand": True,
            "enable_colors": True,
            "enable_menu_animations": True,
            "animation_speed_multiplier": 1.0,
            "color_theme": "default", # <-- NEW SETTING
        }

    def load(self):
        """Loads settings from the JSONC file."""
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                user_settings = json5.load(f)
                self.data.update(user_settings)
        except (FileNotFoundError, Exception):
            self.save()

    ### MODIFIED: The save method is now more robust ###
    def save(self):
        """Saves the current settings to the JSONC file in a strict, compatible format."""
        with open(self.path, 'w', encoding='utf-8') as f:
            # Use dumps with options to ensure strict JSON compatibility
            f.write(json5.dumps(
                self.data, 
                indent=2, 
                quote_keys=True,       # <-- THIS IS THE KEY: Forces keys to be double-quoted
                trailing_commas=False  # <-- Good practice: Removes trailing commas
            ))

    def get(self, key: str, default=None):
        """Gets a setting value by key."""
        return self.data.get(key, default)

    def set(self, key: str, value):
        """Sets a setting value and saves it."""
        self.data[key] = value
        self.save()

# --- Global Settings Instance ---
SETTINGS_FILE = Path("data/settings.jsonc")
settings_manager = Settings(SETTINGS_FILE)
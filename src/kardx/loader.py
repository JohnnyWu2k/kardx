"""Load packaged and user-editable Kard-X data files."""

import json5
import os
import shutil
from importlib import resources
from pathlib import Path


DATA_PACKAGE = f"{__package__}.data"


def get_user_data_dir() -> Path:
    """Return the directory where user-editable game data is stored."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "Kard-X" / "data"
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "kardx" / "data"


def get_user_data_path(filename: str) -> Path:
    return get_user_data_dir() / filename


def get_fallback_data_dir() -> Path:
    return Path.cwd() / ".kardx" / "data"


def load_json5_data(file_path: Path) -> dict | list | None:
    """Loads and parses data from a JSON5 file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json5.load(f)
    except FileNotFoundError:
        print(f"Error: Data file not found at {file_path}")
        return None
    except Exception as e:
        print(f"Error: Failed to parse data file: {e}")
        return None


def load_packaged_json5_data(filename: str) -> dict | list | None:
    """Load a JSON5 file bundled in the kardx.data package."""
    try:
        data_file = resources.files(DATA_PACKAGE).joinpath(filename)
        with data_file.open('r', encoding='utf-8') as f:
            return json5.load(f)
    except FileNotFoundError:
        print(f"Error: Packaged data file not found: {filename}")
        return None
    except Exception as e:
        print(f"Error: Failed to parse packaged data file '{filename}': {e}")
        return None


def merge_game_data(base: dict | list | None, override: dict | list | None) -> dict | list | None:
    """Merge editable user data over packaged defaults when the structure supports it."""
    if override is None:
        return base
    if base is None:
        return override
    if isinstance(base, dict) and isinstance(override, dict):
        merged = dict(base)
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = merge_game_data(merged[key], value)
            else:
                merged[key] = value
        return merged
    if isinstance(base, list) and isinstance(override, list):
        base_items_by_id = {
            item.get("id"): item
            for item in base
            if isinstance(item, dict) and item.get("id")
        }
        override_items_by_id = {
            item.get("id"): item
            for item in override
            if isinstance(item, dict) and item.get("id")
        }
        if len(base_items_by_id) == len(base) and len(override_items_by_id) == len(override):
            merged = []
            seen = set()
            for item in base:
                item_id = item["id"]
                if item_id in override_items_by_id:
                    merged.append(merge_game_data(item, override_items_by_id[item_id]))
                else:
                    merged.append(item)
                seen.add(item_id)
            for item in override:
                if item["id"] not in seen:
                    merged.append(item)
            return merged
    return override


def load_game_data(filename: str) -> dict | list | None:
    """Load user-edited data when present, otherwise fall back to packaged data."""
    packaged_data = load_packaged_json5_data(filename)
    user_path = get_user_data_path(filename)
    if user_path.exists():
        return merge_game_data(packaged_data, load_json5_data(user_path))
    fallback_path = get_fallback_data_dir() / filename
    if fallback_path.exists():
        return merge_game_data(packaged_data, load_json5_data(fallback_path))
    return packaged_data


def ensure_editable_data_file(filename: str) -> Path:
    """
    Return a writable user data path, copying the packaged default there first
    when the user has not created an editable version yet.
    """
    user_path = get_user_data_path(filename)
    try:
        user_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        user_path = get_fallback_data_dir() / filename
        user_path.parent.mkdir(parents=True, exist_ok=True)
    if not user_path.exists():
        packaged_file = resources.files(DATA_PACKAGE).joinpath(filename)
        with resources.as_file(packaged_file) as source_path:
            shutil.copyfile(source_path, user_path)
    return user_path

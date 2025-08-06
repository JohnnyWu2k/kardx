# src/loader.py
import json5
from pathlib import Path

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
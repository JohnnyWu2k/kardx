"""Named, versioned world saves written atomically outside the installation."""
import json
import os
import uuid
from pathlib import Path
from kardx.persistence import atomic_write_text


def save_directory():
    base = Path(os.environ.get("APPDATA", Path.home() / ".local" / "share"))
    return base / "Kard-X" / "worlds"


def new_world(name):
    name = name.strip()
    if not name or len(name) > 40 or any(ord(char) < 32 for char in name):
        raise ValueError("World name must contain 1-40 printable characters")
    return {"id": uuid.uuid4().hex, "name": name, "version": 1}


def world_path(world_id):
    if not isinstance(world_id, str) or len(world_id) != 32 or any(c not in "0123456789abcdef" for c in world_id):
        raise ValueError("Invalid world ID")
    return save_directory() / f"{world_id}.json"


def write_world(document):
    path = world_path(document["id"])
    atomic_write_text(path, json.dumps(document, ensure_ascii=False, allow_nan=False))
    return path


def read_world(world_id):
    from ttx.net.protocol import valid_snapshot, valid_command
    path = world_path(world_id)
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("World file is too large")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("id") != world_id or data.get("version") != 1:
        raise ValueError("Unsupported world save")
    new_world(data.get("name", ""))
    profiles = data.get("profiles", {})
    state = data.get("state", {})
    if not isinstance(profiles, dict) or len(profiles) > 1000:
        raise ValueError("Invalid player records")
    probe = {**state, "client_id": "check", "players": {"check": {"x": 1, "y": 1}}}
    if not valid_snapshot(probe) or not 48 <= state["world_height"] <= 4096 or not 32 <= state["world_width"] <= 4096:
        raise ValueError("Invalid world data")
    for profile in profiles.values():
        if not valid_snapshot({**probe, "players": {"check": profile}}) or ("card_progress" in profile and not valid_command({"card_progress": profile["card_progress"]})):
            raise ValueError("Invalid saved player")
    return data


def list_worlds():
    result = []
    for path in sorted(save_directory().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = read_world(path.stem)
            result.append({"id": data["id"], "name": data["name"]})
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return result


def player_identity():
    path = save_directory().parent / "player-id.txt"
    try:
        value = path.read_text(encoding="ascii").strip()
        return uuid.UUID(value).hex
    except (OSError, ValueError):
        value = uuid.uuid4().hex
        atomic_write_text(path, value)
        return value

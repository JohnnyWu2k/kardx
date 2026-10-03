"""Protect existing progress and settings against invalid input and failed writes."""

import json
from unittest.mock import patch

import pytest

from kardx.loader import load_packaged_json5_data
from kardx.sandbox import SandboxGame
from kardx.scenes.sandbox.sandbox_controller import SandboxController
from kardx.settings import Settings


@pytest.fixture
def sandbox():
    with patch("kardx.sandbox.load_game_data", side_effect=load_packaged_json5_data):
        game = SandboxGame()
        game.start("player_balanced")
    return game


@pytest.mark.parametrize("slot", ["../escape", "nested/slot", "nested\\slot", "C:slot", "", "."])
def test_save_slot_cannot_escape_its_directory(sandbox, tmp_path, slot):
    with pytest.raises(ValueError, match="slot"):
        sandbox.save(slot, tmp_path)
    with pytest.raises(ValueError, match="slot"):
        sandbox.load(slot, tmp_path)


@pytest.mark.parametrize("change", [
    {"deck_ids": "strike"}, {"inventory": {"wood": -1}},
    {"current_hp": 9999}, {"current_hp": 0}, {"base_mana": -1},
    {"max_hp": True}, {"player_id": "missing"}, {"deck_ids": ["missing"]},
    {"current_room": "missing"}, {"flags": "flag"}, {"turn_count": -1},
])
def test_invalid_save_does_not_replace_active_game(sandbox, tmp_path, change):
    payload = sandbox.state.to_dict()
    payload.update(change)
    (tmp_path / "broken.json").write_text(json.dumps(payload), encoding="utf-8")
    previous = sandbox.state
    with pytest.raises(ValueError):
        sandbox.load("broken", tmp_path)
    assert sandbox.state is previous


def test_failed_save_replace_keeps_previous_progress(sandbox, tmp_path):
    path = sandbox.save("slot", tmp_path)
    previous = path.read_bytes()
    sandbox.state.gold += 50
    with patch("os.replace", side_effect=OSError("disk failure")):
        with pytest.raises(OSError):
            sandbox.save("slot", tmp_path)
    assert path.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [path]


def test_corrupt_save_is_reported_in_the_command_loop(sandbox):
    controller = SandboxController.__new__(SandboxController)
    controller.game = sandbox
    with patch.object(sandbox, "load", side_effect=ValueError("invalid save")):
        assert controller._handle_command("load bad") == "continue"
    assert "invalid save" in " ".join(controller.messages)


def test_settings_read_does_not_write_a_missing_file(tmp_path):
    path = tmp_path / "settings.jsonc"
    settings = Settings(path)
    assert settings.get("enable_colors") == load_packaged_json5_data("settings.jsonc")["enable_colors"]
    assert not path.exists()


def test_invalid_settings_are_safe_and_original_file_is_preserved(tmp_path):
    path = tmp_path / "settings.jsonc"
    path.write_text('{"color_theme":"missing", "animation_speed_multiplier":"fast", "enable_colors":null}', encoding="utf-8")
    previous = path.read_bytes()
    settings = Settings(path)
    assert settings.get("color_theme") == "default"
    assert settings.get("animation_speed_multiplier") == 1.0
    assert settings.get("enable_colors") == load_packaged_json5_data("settings.jsonc")["enable_colors"]
    assert path.read_bytes() == previous


def test_malformed_settings_are_not_silently_overwritten(tmp_path):
    path = tmp_path / "settings.jsonc"
    path.write_text("{unfinished", encoding="utf-8")
    settings = Settings(path)
    assert settings.get("color_theme") == "default"
    assert path.read_text(encoding="utf-8") == "{unfinished"


def test_failed_settings_replace_keeps_previous_file(tmp_path):
    path = tmp_path / "settings.jsonc"
    path.write_text('{"color_theme":"ocean"}', encoding="utf-8")
    settings = Settings(path)
    previous = path.read_bytes()
    settings.data["color_theme"] = "forest"
    with patch("os.replace", side_effect=OSError("disk failure")):
        with pytest.raises(OSError):
            settings.save()
    assert path.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [path]


def test_saved_fallback_settings_survive_restart(tmp_path):
    primary = tmp_path / "global" / "settings.jsonc"
    primary.parent.mkdir()
    primary.write_text('{"color_theme":"default"}', encoding="utf-8")
    fallback = tmp_path / ".kardx" / "settings.jsonc"
    fallback.parent.mkdir()
    fallback.write_text('{"color_theme":"ocean"}', encoding="utf-8")
    with patch("kardx.settings._default_settings_file", return_value=primary), patch("pathlib.Path.cwd", return_value=tmp_path):
        settings = Settings(primary)
    assert settings.path == fallback
    assert settings.get("color_theme") == "ocean"

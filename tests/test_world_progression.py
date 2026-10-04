import curses
import json
import socket
import threading
import time
from copy import deepcopy
from unittest.mock import Mock, patch

import pytest

from ttx.net import server, discovery
from ttx.net.protocol import JsonLineReader, SNAPSHOT_LIMIT, valid_command, valid_snapshot
from ttx.world import storage
from ttx.world.crafting import craft
from ttx.text_input import edit_text, read_text_key
from kardx.scenes.game.game_view import GameView
from ttx.combat.card_battle import prepare_card_battle
from test_mouse_experience import world, mouse, point


@pytest.fixture
def isolated_world(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "save_directory", lambda: tmp_path / "worlds")
    server.reset_game_state(512, 192, seed=42)
    server.objects.clear()
    server.enemies.clear()
    server.players["p"] = {"x": 10, "y": 21, "inventory": {}, "cards": []}
    yield
    server.stop_server()
    server.players.clear()


def test_progression_requires_workbench_tools_and_atomic_costs(isolated_world):
    player = server.players["p"]
    player["inventory"] = {"wood": 12}
    inv = player["inventory"]
    assert craft(inv, "sticks", False) == "Crafted 4 stick"
    before = deepcopy(inv)
    assert "workbench" in craft(inv, "wood_pickaxe", False)
    assert inv == before
    craft(inv, "workbench", False)
    server.process_message("p", {"build": True, "x": 11, "y": 21, "material": "workbench"})
    assert server.custom_tiles["11,21"]["char"] == "W"
    server.process_message("p", {"craft": "wood_pickaxe"})
    assert inv["wood_pickaxe"] == 1
    server.custom_tiles["10,22"] = {"x": 10, "y": 22, "char": "o"}
    server.process_message("p", {"gather": True, "dx": 0, "dy": 1})
    assert server.custom_tiles["10,22"]["char"] == "o"
    assert "stone_pickaxe" in player["notice"]
    inv["stone_pickaxe"] = 1
    server.process_message("p", {"gather": True, "dx": 0, "dy": 1})
    assert inv["iron_ore"] == 1
    assert server.custom_tiles["10,22"]["char"] == "."
    del inv["wood_pickaxe"]
    del inv["stone_pickaxe"]
    server.custom_tiles["10,22"]["char"] = "#"
    server.process_message("p", {"gather": True, "dx": 0, "dy": 1})
    assert "wood_pickaxe" in player["notice"]
    assert server.custom_tiles["10,22"]["char"] == "#"


def test_craft_far_from_bench_and_malformed_commands_do_not_consume(isolated_world):
    player = server.players["p"]
    player["inventory"] = {"wood": 30, "stick": 20}
    server.custom_tiles["25,21"] = {"x": 25, "y": 21, "char": "W"}
    before = deepcopy(player["inventory"])
    server.process_message("p", {"craft": "wood_pickaxe"})
    assert player["inventory"] == before
    for command in ({"hello": "../x"}, {"craft": []}, {"save": "yes"}, {"card_progress": {}}):
        assert not valid_command(command)


def test_unicode_editing_preserves_names_and_backspace():
    screen = Mock()
    screen.get_wch.side_effect = ["中", "文", "\n"]
    text = edit_text("", read_text_key(screen))
    text = edit_text(text, read_text_key(screen))
    assert text == "中文"
    assert read_text_key(screen) == 10
    assert edit_text(text, curses.KEY_BACKSPACE) == "中"
    assert storage.new_world("中文世界")["name"] == "中文世界"


def test_ime_text_does_not_override_native_movement(world):
    from ttx.input import MotionInput
    controls = world._controls = MotionInput(lambda: (1, False))
    # An IME can commit a different letter long after the physical key event.
    world.process_key(ord("a"))
    world.process_key(ord("w"))
    assert not controls.tap_pending and not controls.jump_pending
    assert controls.sample() == (1, False)


def test_pseudoconsole_uses_resolved_owner_for_physical_input():
    from test_terminal import window_api
    from ttx.input import windows_key_state
    api = window_api("PseudoConsoleWindow")
    api.GetAsyncKeyState.side_effect = lambda key: 0x8000 if key == 0x44 else 0
    with patch("ttx.input.os.name", "nt"), patch("ttx.input.sys.stdin.isatty", return_value=True), patch(
        "ttx.input.ctypes.WinDLL", return_value=api, create=True
    ), patch("ttx.input.pseudoconsole_window", return_value=42):
        sample = windows_key_state()
        assert sample() == (1, False)
        api.GetForegroundWindow.return_value = 999
        assert sample() == (0, False)


def test_named_world_unicode_entry_uses_wide_input():
    from ttx.cli import name_world
    from ttx.terminal import TerminalRenderer
    from test_mouse_experience import Screen
    screen = Screen()
    screen.get_wch = Mock(side_effect=["中", "文", "世", "界", "\n"])
    assert name_world(screen, TerminalRenderer(screen)) == "中文世界"


def test_right_empty_hides_aim_and_left_restores_without_build(world):
    world._target_tile = Mock(return_value=".")
    mouse(world, *point(world, 22, 20), curses.BUTTON3_PRESSED)
    assert world.aim_visible is False
    world._send.assert_not_called()
    mouse(world, *point(world, 22, 20), curses.BUTTON1_PRESSED)
    assert world.aim_visible is True


def test_vital_delta_shows_hp_loss_mana_spend_and_defense():
    game = prepare_card_battle("enemy_giant_rat")
    actor = game.player
    view = GameView()
    actor.mana = 3
    view._vital_lines(actor, 60)
    actor.hp -= 6
    actor.mana -= 2
    actor.defend += 5
    lines = view._vital_lines(actor, 60)
    assert "-6" in lines[0] and "-2" in lines[1] and "+5" in lines[1]
    assert "\033[1;7m" in lines[0]


def await_player(sock, predicate):
    reader = JsonLineReader(SNAPSHOT_LIMIT)
    deadline = time.monotonic() + 3
    sock.settimeout(0.2)
    while time.monotonic() < deadline:
        try:
            for state in reader.feed(sock.recv(65536)):
                if predicate(state):
                    assert valid_snapshot(state)
                    return state
        except socket.timeout:
            continue
    raise AssertionError("Timed out waiting for snapshot")


def test_real_server_world_save_disconnect_load_restores_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "save_directory", lambda: tmp_path / "worlds")
    document = storage.new_world("測試世界")
    token = "a" * 32
    handle = server.start_server(100, 30, False, host="127.0.0.1", port=0, document=document)
    try:
        with socket.create_connection(("127.0.0.1", handle.port)) as sock:
            sock.sendall((json.dumps({"hello": token}) + "\n").encode())
            state = await_player(sock, lambda s: s["players"][s["client_id"]].get("profile_ready"))
            client_id = state["client_id"]
            with server.state_lock:
                server.players[client_id]["inventory"] = {"wood": 9, "stone_pickaxe": 1}
                server.custom_tiles["12,21"] = {"x": 12, "y": 21, "char": "W"}
                seed = server.map_seed
            order = [None] * 25
            order[9], order[24] = "stone_pickaxe", "wood"
            sock.sendall((json.dumps({"inventory_order": order}) + "\n").encode())
            await_player(sock, lambda s: s["players"][s["client_id"]].get("inventory_order") == order)
            sock.sendall(b'{"save":true}\n')
            await_player(sock, lambda s: s["players"][s["client_id"]].get("notice") == "World saved")
    finally:
        handle.stop()
    saved = storage.read_world(document["id"])
    assert saved["name"] == "測試世界"
    assert saved["profiles"][token]["inventory"]["wood"] == 9
    assert saved["profiles"][token]["inventory_order"] == order
    assert storage.list_worlds()[0]["id"] == document["id"]
    handle = server.start_server(100, 30, False, host="127.0.0.1", port=0, document=saved)
    try:
        with socket.create_connection(("127.0.0.1", handle.port)) as sock:
            sock.sendall((json.dumps({"hello": token}) + "\n").encode())
            state = await_player(sock, lambda s: s["players"][s["client_id"]].get("profile_ready"))
            assert state["map_seed"] == seed
            assert state["custom_tiles"]["12,21"]["char"] == "W"
            assert state["players"][state["client_id"]]["inventory"]["stone_pickaxe"] == 1
            assert state["players"][state["client_id"]]["inventory_order"] == order
    finally:
        handle.stop()


def test_lan_discovery_with_real_udp_responder(monkeypatch):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    monkeypatch.setattr(discovery, "DISCOVERY_PORT", port)
    stop, ready = threading.Event(), threading.Event()
    thread = threading.Thread(target=discovery.advertise, args=(stop, lambda: {"name": "LAN Test", "port": 12345}, ready))
    thread.start()
    try:
        assert ready.wait(1)
        found = discovery.discover(0.3)
        assert any(result["name"] == "LAN Test" and result["port"] == 12345 for result in found)
    finally:
        stop.set()
        thread.join(1)
    assert not thread.is_alive()


def test_failed_host_bind_does_not_overwrite_existing_save(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "save_directory", lambda: tmp_path / "worlds")
    document = storage.new_world("Existing")
    storage.write_world(document)
    original = storage.world_path(document["id"]).read_bytes()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        with pytest.raises(OSError):
            server.start_server(100, 30, False, host="127.0.0.1", port=listener.getsockname()[1], document=document)
    assert storage.world_path(document["id"]).read_bytes() == original

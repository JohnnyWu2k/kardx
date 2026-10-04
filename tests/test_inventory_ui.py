import curses
from copy import deepcopy
from unittest.mock import Mock, patch

import pytest

from ttx.inventory_ui import backpack_frame
from ttx.net import client, server
from ttx.net.protocol import valid_command
from ttx.terminal import Frame, TerminalRenderer
from ttx.world.camera import Camera
from ttx.world.inventory import sync_slots, HOTBAR_SIZE, BACKPACK_SIZE
from test_mouse_experience import world, mouse, point, Screen
from test_world_progression import isolated_world


def test_slots_only_contain_owned_items_and_do_not_shuffle_existing_stacks():
    slots = sync_slots([], {"dirt": 0, "wood": 3, "stone": 2})
    assert len(slots) == 25 and slots[:3] == ["wood", "stone", None]
    slots[11], slots[1] = slots[1], None
    updated = sync_slots(slots, {"wood": 0, "stone": 4, "coal": 1})
    assert updated[11] == "stone" and updated[0] == "coal"
    assert updated.count("stone") == 1 and "wood" not in updated


def test_empty_hotbar_has_ten_numbered_rows_and_no_duplicate_summary(world):
    world.card_hp = None
    world._canvas = Frame(40, 120)
    client.game_state["players"]["p"]["inventory"] = {"dirt": 0}
    world._draw_ui_panel(90, 30, 40)
    lines = ["".join(char for char, _ in row) for row in world._canvas.cells]
    assert "dirt" not in "\n".join(lines) and "x0" not in "\n".join(lines)
    for index in range(10):
        assert f"{index + 1}:" in lines[3 + index]
    client.game_state["players"]["p"]["inventory"] = {"stone": 5}
    world._canvas = Frame(40, 120)
    world._draw_ui_panel(90, 30, 40)
    text = "\n".join("".join(char for char, _ in row) for row in world._canvas.cells)
    assert text.count("stone") == 1


def test_ten_hotbar_keys_and_mouse_wheel_wrap(world):
    for key, index in zip("1234567890", range(10)):
        world.process_key(ord(key))
        assert world.active_inventory_slot == index
    mouse(world, 0, 0, curses.BUTTON4_PRESSED)
    assert world.active_inventory_slot == 8
    world.process_key(ord("1"))
    mouse(world, 0, 0, curses.BUTTON4_PRESSED)
    assert world.active_inventory_slot == 9


def test_selected_block_places_without_build_mode_and_bare_hands_mine(world):
    client.game_state["enemies"] = {}
    mouse(world, *point(world, 21, 20), curses.BUTTON1_PRESSED)
    world._send.assert_called_once_with({"build": True, "x": 21, "y": 20, "material": "wood"})
    mouse(world, *point(world, 21, 20), curses.BUTTON1_RELEASED)
    world._send.reset_mock()
    world.process_key(ord("0"))
    mouse(world, *point(world, 21, 20), curses.BUTTON1_PRESSED)
    world._send.assert_called_once_with({"gather": True, "dx": 1, "dy": 0, "tool": None})


def test_selected_tool_is_sent_and_pointer_motion_never_gathers(world):
    client.game_state["enemies"] = {}
    client.game_state["players"]["p"]["inventory"]["wood_pickaxe"] = 1
    world.process_key(ord("2"))
    mouse(world, *point(world, 21, 20), 0)
    assert world._mouse_target() == (21, 20)
    mouse(world, *point(world, 20, 21), 0)
    assert world._mouse_target() == (20, 21)
    world._send.assert_not_called()
    mouse(world, *point(world, 20, 21), curses.BUTTON1_PRESSED)
    world._send.assert_called_once_with({"gather": True, "dx": 0, "dy": 1, "tool": "wood_pickaxe"})


def test_right_click_always_hides_aim_without_opening_menus(world):
    world._craft_menu = Mock()
    for tile in ("#", ".", "W"):
        world._target_tile = Mock(return_value=tile)
        world.aim_visible = True
        mouse(world, *point(world, 21, 20), curses.BUTTON3_PRESSED)
        assert not world.aim_visible
        mouse(world, *point(world, 20, 21), 0)
        assert not world.aim_visible
    world._craft_menu.assert_not_called()
    world._send.assert_not_called()


@pytest.mark.parametrize("size", [(50, 210), (24, 80), (16, 40), (12, 17), (1, 1)])
def test_backpack_overlay_bounds_and_all_25_targets(size):
    background = Frame(*size)
    background.addstr(0, 0, "WORLD")
    slots = sync_slots([], {"stone": 12, "wood_pickaxe": 1})
    before = deepcopy(background.cells)
    frame, targets = backpack_frame(background, slots, {"stone": 12, "wood_pickaxe": 1}, 24, 0)
    assert background.cells == before
    if min(size) > 1:
        assert len(targets) == 25
        assert all(0 <= x < right <= size[1] and 0 <= y < bottom <= size[0] for x, y, right, bottom, _ in targets)
        x, y, _, _, _ = targets[-1]
        assert frame.cells[y][x][1] == curses.A_REVERSE


def test_backpack_hover_swap_close_freezes_world_and_restores_input(world):
    world.stdscr = Screen()
    world._stop_event = None
    world._stop_controls = Mock()
    world._request_pause = Mock()
    world._controls = Mock()
    world.inventory = ["wood"] + [None] * 11 + ["stone"] + [None] * 12
    client.game_state["players"]["p"]["inventory"]["stone"] = 5
    original = world.inventory.copy()
    world._compose_frame = Mock(return_value=Frame(30, 120))
    world._renderer = TerminalRenderer(world.stdscr)
    _, targets = backpack_frame(Frame(30, 120), original, {"wood": 5, "stone": 5}, 0, 0)
    x, y, _, _, _ = targets[12]
    world.stdscr.keys.extend([curses.KEY_MOUSE, ord("0"), ord("e")])
    with patch.object(curses, "getmouse", return_value=(0, x, y, 0, 0)), patch.object(curses, "flushinp"):
        world.process_key(ord("e"))
    assert world.inventory[9] == "stone" and world.inventory[12] is None
    assert world.active_inventory_slot == 9
    assert not world._paused
    world._stop_controls.assert_called_once()
    world._compose_frame.assert_called_once()
    assert world._request_pause.call_args_list[0].args == (True,)
    assert world._request_pause.call_args_list[-1].args == (False,)
    world._controls.reset.assert_called_once()
    world._send.assert_called_once_with({"inventory_order": world.inventory})


def test_server_checks_selected_tool_and_rejects_unowned_tools(isolated_world):
    player = server.players["p"]
    player["inventory"] = {"wood_pickaxe": 1, "iron_pickaxe": 1}
    server.custom_tiles["11,21"] = {"x": 11, "y": 21, "char": "o"}
    for tool in (None, "wood_pickaxe"):
        server.process_message("p", {"gather": True, "dx": 1, "dy": 0, "tool": tool})
        assert server.custom_tiles["11,21"]["char"] == "o"
    player["inventory"]["iron_pickaxe"] = 0
    server.process_message("p", {"gather": True, "dx": 1, "dy": 0, "tool": "iron_pickaxe"})
    assert server.custom_tiles["11,21"]["char"] == "o"
    player["inventory"]["iron_pickaxe"] = 1
    server.process_message("p", {"gather": True, "dx": 1, "dy": 0, "tool": "iron_pickaxe"})
    assert server.custom_tiles["11,21"]["char"] == "."


def test_slot_order_is_validated_and_sanitized_while_paused(isolated_world):
    player = server.players["p"]
    player.update(paused=True, inventory={"wood": 4, "stone": 2})
    slots = [None] * 25
    slots[9], slots[24] = "stone", "wood"
    server.process_message("p", {"inventory_order": slots})
    assert player["inventory_order"] == slots
    slots[0] = "unowned"
    server.process_message("p", {"inventory_order": slots})
    assert "unowned" not in player["inventory_order"]
    assert player["inventory"] == {"wood": 4, "stone": 2}
    for order in ([None], ["wood"] * 25, [None] * 24 + [{}]):
        assert not valid_command({"inventory_order": order})
    assert not valid_command({"tool": []})


@pytest.mark.parametrize("axis,direction", [(0, 1), (0, -1), (1, 1), (1, -1)])
def test_camera_changes_once_while_walking_into_the_new_page(axis, direction):
    camera = Camera()
    visible, world_size = (40, 20), (512, 192)
    start = camera.follow((100, 90), visible, world_size, now=0)
    player = [100, 90]
    player[axis] = start[axis] + (visible[axis] - 1 if direction > 0 else .9)
    target = camera.follow(player, visible, world_size, now=1)
    assert target != start
    for step in range(1, 27):
        player[axis] += direction * .2
        current = camera.follow(player, visible, world_size, now=1 + step / 60)
        assert current == camera.position == target


def test_camera_switches_both_axes_in_one_frame_at_a_corner():
    camera = Camera()
    start = camera.follow((100, 90), (40, 30), (512, 192), now=0)
    target = camera.follow((119, 104), (40, 30), (512, 192), now=1)
    assert all(b > a for a, b in zip(start, target))
    assert camera.follow((120, 105), (40, 30), (512, 192), now=1.01) == target


def test_pause_mouse_hover_selects_without_clicking(world):
    world.stdscr = Screen()
    world.stdscr.keys.extend([curses.KEY_MOUSE, 10])
    world._stop_event = None
    world.quit_to_menu = False
    world._stop_controls = Mock()
    world._request_pause = Mock()
    world._controls = Mock()
    world._compose_frame = Mock(return_value=Frame(30, 120))
    world._renderer = TerminalRenderer(world.stdscr)
    with patch.object(curses, "getmouse", return_value=(0, 50, 16, 0, 0)), patch.object(curses, "flushinp"):
        assert not world._pause()
    assert world.quit_to_menu


def test_windows_mouse_motion_disables_quick_edit_and_restores_mode():
    import ctypes
    from ttx import mouse as mouse_module
    kernel = Mock()
    kernel.GetStdHandle.return_value = 42
    current = [0x0047]  # Quick Edit enabled by the terminal before the game.
    def get_mode(handle, mode):
        mode._obj.value = current[0]
        return 1
    def set_mode(handle, mode):
        current[0] = mode
        return 1
    kernel.GetConsoleMode.side_effect = get_mode
    kernel.SetConsoleMode.side_effect = set_mode
    with patch.object(mouse_module.os, "name", "nt"), patch.object(mouse_module.sys.stdin, "isatty", return_value=True), patch.object(
        ctypes, "WinDLL", return_value=kernel, create=True
    ), patch.object(mouse_module, "_console_mouse", None):
        mouse_module._windows_motion(True)
        assert current[0] & 0x0010 and current[0] & 0x0080 and not current[0] & 0x0040
        mouse_module._windows_motion(True)
        mouse_module._windows_motion(False)
        assert current[0] == 0x0047

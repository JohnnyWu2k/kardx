"""Held world actions use a clock, current aim, and explicit release/cancel."""
import curses
from unittest.mock import Mock, patch

import pytest

from ttx.input import MotionInput
from ttx.net import client
from test_mouse_experience import world, mouse, point


def press(game, x=21, y=20):
    with patch.object(client.time, "monotonic", return_value=0):
        mouse(game, *point(game, x, y), curses.BUTTON1_PRESSED)


def test_hold_places_on_a_clock_and_drag_packets_do_not_bypass_rate_limit(world):
    press(world)
    for _ in range(20):
        mouse(world, *point(world, 20, 21), curses.BUTTON1_PRESSED | curses.REPORT_MOUSE_POSITION)
        world._update_mouse_action(.05)
    assert world._send.call_count == 1
    world._update_mouse_action(.13)
    world._send.assert_called_with({"build": True, "x": 20, "y": 21, "material": "wood"})
    assert world._send.call_count == 2
    world._update_mouse_action(20)  # A stalled frame emits one action, no burst.
    assert world._send.call_count == 3
    world._update_mouse_action(20.01)
    assert world._send.call_count == 3


@pytest.mark.parametrize("tool", [None, "wood_pickaxe"])
def test_hold_mines_with_the_selected_tool_or_bare_hand_and_current_pointer(world, tool):
    client.game_state["enemies"] = {}
    if tool:
        client.game_state["players"]["p"]["inventory"][tool] = 1
    world.process_key(ord("2"))
    world._target_tile = Mock(return_value=":")
    press(world)
    mouse(world, *point(world, 20, 21), 0)
    world._update_mouse_action(.13)
    assert world._send.call_count == 2
    world._send.assert_called_with({"gather": True, "dx": 0, "dy": 1, "tool": tool})
    world._update_mouse_action(.26)
    assert world._send.call_count == 3  # Stationary hold needs no new mouse events.


def test_repeat_reprojects_pointer_after_camera_change(world):
    press(world)
    world._display_camera = (11.25, 15.5)
    world._update_mouse_action(.13)
    world._send.assert_called_with({"build": True, "x": 22, "y": 20, "material": "wood"})


@pytest.mark.parametrize("cancel", ["release", "right", "wheel", "slot", "panel", "outside", "pause", "stop"])
def test_hold_cancels_and_does_not_resume_on_pointer_motion(world, cancel):
    press(world)
    if cancel == "release":
        mouse(world, -1, -1, curses.BUTTON1_RELEASED)
    elif cancel == "right":
        mouse(world, *point(world, 21, 20), curses.BUTTON3_PRESSED)
    elif cancel == "wheel":
        mouse(world, 0, 0, curses.BUTTON4_PRESSED)
    elif cancel == "slot":
        world.process_key(ord("2"))
    elif cancel == "panel":
        mouse(world, 100, 7, curses.BUTTON1_PRESSED | curses.REPORT_MOUSE_POSITION)
        assert world.active_inventory_slot == 0  # A drag cannot select UI slots.
    elif cancel == "outside":
        mouse(world, -1, -1, 0)
    elif cancel == "pause":
        world._paused = True
        world._update_mouse_action(.13)
        world._paused = False
    else:
        world._stop_controls()
    world._send.reset_mock()
    mouse(world, *point(world, 20, 21), 0)
    world._update_mouse_action(10)
    world._send.assert_not_called()


def test_native_release_or_focus_loss_cancels_even_without_terminal_release_event(world):
    native = Mock(return_value=(0, False))
    native.mouse_down = Mock(return_value=True)
    world._controls = MotionInput(native)
    press(world)
    world._update_mouse_action(.13)
    assert world._send.call_count == 2
    native.mouse_down.return_value = False
    world._update_mouse_action(.26)
    native.mouse_down.return_value = True
    world._update_mouse_action(.39)
    assert world._send.call_count == 2
    assert not world._mouse_down


def test_atomic_click_is_one_action_and_release_allows_a_fresh_press(world):
    mouse(world, *point(world, 21, 20), curses.BUTTON1_CLICKED)
    world._update_mouse_action(10)
    assert world._send.call_count == 1
    press(world)
    world._update_mouse_action(.13)
    assert world._send.call_count == 3
    mouse(world, *point(world, 21, 20), curses.BUTTON1_RELEASED)
    world._update_mouse_action(20)
    press(world)
    assert world._send.call_count == 4


def test_depleted_blocks_stop_instead_of_mining_or_placing_an_autofilled_item(world):
    press(world)
    client.game_state["players"]["p"]["inventory"] = {"wood": 0, "dirt": 3}
    world._update_mouse_action(.13)
    assert world._send.call_count == 1
    assert world._mouse_action is None


def test_repeats_skip_occupied_or_out_of_reach_tiles_without_spamming_notices(world):
    press(world)
    world._notify = Mock()
    world._prediction_blocked.return_value = True
    world._update_mouse_action(.13)
    world._prediction_blocked.return_value = False
    mouse(world, *point(world, 25, 20), 0)
    world._update_mouse_action(.26)
    assert world._send.call_count == 1
    world._notify.assert_not_called()
    mouse(world, *point(world, 20, 21), 0)
    world._update_mouse_action(.39)
    assert world._send.call_count == 2


def test_mining_skips_air_gathers_foreground_objects_and_never_auto_starts_combat(world):
    client.game_state["enemies"] = {}
    world.process_key(ord("2"))
    world._fight_adjacent_enemy = Mock()
    press(world)
    world._update_mouse_action(.13)
    assert world._send.call_count == 1
    client.game_state["objects"] = {"tree": {"x": 21, "y": 20}}
    world._update_mouse_action(.26)
    assert world._send.call_count == 2
    client.game_state["enemies"] = {"rat": {"x": 21, "y": 20}}
    world._update_mouse_action(.39)
    world._fight_adjacent_enemy.assert_not_called()
    assert world._send.call_count == 2 and world._mouse_action is None


def test_mouse_press_in_panel_cannot_start_a_world_hold_by_dragging_out(world):
    mouse(world, 100, 3, curses.BUTTON1_PRESSED)
    mouse(world, *point(world, 21, 20), curses.BUTTON1_PRESSED | curses.REPORT_MOUSE_POSITION)
    world._update_mouse_action(10)
    world._send.assert_not_called()

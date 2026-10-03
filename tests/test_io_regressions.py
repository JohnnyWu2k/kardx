"""Unicode composition, legacy screen ownership, tty reads and cache lifetime."""

import gc
import importlib.util
import io
import sys
import types
import weakref
from pathlib import Path
from unittest.mock import Mock, patch

import curses
import pytest

from kardx import keyboard, view_utils
from kardx.card import Card
from kardx.player import Player
from kardx.scenes.game.game_view import GameView
from kardx.scenes.sandbox.sandbox_view import SandboxView
from ttx.terminal import Frame
from ttx.net.client import Game as WorldGame
from ttx.world.map import InfiniteGameMap


def test_overwriting_a_wide_continuation_clears_its_old_leading_cell():
    frame = Frame(1, 4)
    frame.addstr(0, 0, "中ab")
    frame.addstr(0, 1, "X")
    assert frame.cells[0] == [(" ", 0), ("X", 0), ("a", 0), ("b", 0)]


def test_wide_write_clears_overlapping_wide_characters_on_both_sides():
    frame = Frame(1, 4)
    frame.addstr(0, 0, "中文")
    frame.addch(0, 1, "字")
    assert frame.cells[0] == [(" ", 0), ("字", 0), ("", 0), (" ", 0)]


def test_wide_addch_is_clipped_without_leaving_orphan_cells():
    frame = Frame(1, 3)
    frame.addch(0, 0, "中")
    frame.addch(0, 2, "文")
    assert frame.cells[0] == [("中", 0), ("", 0), (" ", 0)]


def test_ansi_empty_parameters_and_default_foreground_are_safe():
    frame = Frame(1, 3)
    with patch.object(curses, "color_pair", side_effect=lambda pair: pair * 256):
        frame.addstr(0, 0, "\033[31;;1mA\033[39mB")
    assert frame.cells[0][0][1] & curses.A_BOLD
    assert frame.cells[0][1][1] & curses.A_COLOR == 0


def test_clipping_keeps_combining_marks_at_the_right_edge():
    assert view_utils.fit_to_width("e\u0301X", 1) == "e\u0301"


def test_clipping_colored_chinese_text_uses_display_columns():
    text = GameView()._clip_text("\033[31m中文測試\033[0m", 5)
    assert view_utils.get_visible_len(text) == 5
    assert "中文" in text


def test_narrow_card_layout_keeps_the_selected_card_visible():
    hand = [Card(f"card{i}", f"Card{i}", 0, "Attack", "") for i in range(5)]
    player = Player("test", 10, 3, [])
    player.hand = hand
    view = GameView()
    for width, max_lines in ((36, 8), (20, 1)):
        lines = view._format_hand(player, 4, width, max_lines)
        assert "Card4" in "\n".join(lines)
        assert all(view_utils.get_visible_len(line) <= width for line in lines)


def test_sandbox_redraw_invalidates_the_cached_battle_frame():
    output = io.StringIO()
    with patch.object(sys, "stdout", output), patch.object(view_utils, "terminal_size", return_value=(30, 6)):
        view_utils.render_screen(["battle"])
        with patch("kardx.scenes.sandbox.sandbox_view.get_terminal_size", return_value=(30, 6)):
            SandboxView().display(["world"])
        output.seek(0)
        output.truncate()
        view_utils.render_screen(["battle"])
        assert "battle" in output.getvalue()


def test_discarded_world_is_not_retained_by_a_global_method_cache():
    game_map = InfiniteGameMap(120, seed=1)
    game_map.surface_height(20)
    reference = weakref.ref(game_map)
    del game_map
    gc.collect()
    assert reference() is None


def test_resize_during_composition_does_not_change_the_current_frame_layout():
    screen = Mock()
    screen.getmaxyx.side_effect = [(30, 120), (10, 40), (10, 40)]
    game = WorldGame.__new__(WorldGame)
    game.stdscr = screen
    game.game_map = InfiniteGameMap(120, seed=1)
    game.scale = 1
    game.smooth_graphics = True
    game.building_mode_active = False
    game.inventory = ["wood"]
    game.active_inventory_slot = 0
    game.card_hp = None
    game._view_state = lambda _now: {}
    with patch.object(curses, "color_pair", return_value=0):
        frame = game._compose_frame()
    assert frame.rows == game._terrain_frame.rows == 30
    screen.getmaxyx.assert_called_once()


def load_unix_keyboard():
    """Load the actual Unix branch with tty adapters even on Windows CI."""
    spec = importlib.util.spec_from_file_location("_ttx_unix_keyboard_test", Path(keyboard.__file__))
    module = importlib.util.module_from_spec(spec)
    tty = types.SimpleNamespace(setraw=Mock())
    termios = types.SimpleNamespace(tcgetattr=Mock(return_value=[]), tcsetattr=Mock(), TCSADRAIN=0)
    with patch.dict(sys.modules, {"msvcrt": None, "tty": tty, "termios": termios}):
        spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("sequence", [b"\x1b[A", b"\x1bOA", b"\x1b[1;5A"])
@pytest.mark.parametrize("blocking", [True, False])
def test_unix_arrow_reading_bypasses_textio_prefetch(sequence, blocking):
    module = load_unix_keyboard()
    stdin = Mock()
    stdin.fileno.return_value = 42
    stdin.read.side_effect = AssertionError("Buffered text reads can hide escape bytes from select().")
    chunks = [bytes([byte]) for byte in sequence]
    with patch.object(sys, "stdin", stdin), patch.object(module.os, "read", side_effect=chunks), patch.object(
        module.select, "select", return_value=([42], [], [])
    ):
        read = module.get_key if blocking else module.get_key_non_blocking
        assert read() == keyboard.KEY_UP
    module.termios.tcsetattr.assert_called_once()


def test_unix_eof_exits_instead_of_spinning_on_empty_keys():
    module = load_unix_keyboard()
    with patch.object(sys, "stdin", Mock()), patch.object(module.os, "read", return_value=b""):
        with pytest.raises(EOFError):
            module.get_key()
    module.termios.tcsetattr.assert_called_once()


@pytest.mark.parametrize("cost", [-1, 1.5, True, "1"])
def test_invalid_card_cost_is_rejected_before_it_can_break_battle_ui(cost):
    with pytest.raises(ValueError, match="cost"):
        Card("broken", "Broken", cost, "Attack", "")

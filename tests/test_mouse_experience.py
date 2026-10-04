import curses
from collections import deque
from unittest.mock import Mock, patch

import pytest

from kardx.scenes.game.game_view import GameView
from kardx.scenes.pause_menu.pause_menu_view import PauseMenuView
from kardx.view_utils import get_visible_len, use_terminal
from ttx.combat.card_battle import prepare_card_battle
from ttx.net import client
from ttx.terminal import CardTerminal, TerminalRenderer
from ttx.world.render import origin, TILE_PIXELS


@pytest.fixture
def world(monkeypatch):
    game = client.Game.__new__(client.Game)
    game.stdscr = Mock()
    game.stdscr.getmaxyx.return_value = (30, 120)
    game.scale = 1
    game.game_map = None
    game.smooth_graphics = True
    game._display_camera = (10.25, 15.5)
    game.mouse_raw_x = game.mouse_raw_y = None
    game.inventory = ["wood"] + [None] * 24
    game.active_inventory_slot = 0
    game.building_mode_active = False
    game.build_direction = (1, 0)
    game._send = Mock()
    game._prediction_blocked = Mock(return_value=False)
    monkeypatch.setattr(client, "game_state", {
        "client_id": "p", "players": {"p": {"x": 20, "y": 20, "inventory": {"wood": 5}}},
        "enemies": {"rat": {"x": 21, "y": 20}},
    })
    return game


def mouse(game, x, y, state):
    with patch.object(curses, "getmouse", return_value=(0, x, y, 0, state)):
        game.process_key(curses.KEY_MOUSE)


def point(game, x, y):
    ox, oy = origin(game._display_camera)
    return ((x * TILE_PIXELS + TILE_PIXELS // 2 - ox) // 2, (y * TILE_PIXELS + TILE_PIXELS // 2 - oy) // 4)


def test_pointer_uses_rendered_camera_and_panel_never_attacks(world):
    mouse(world, *point(world, 21, 20), 0)
    assert world._mouse_target() == (21, 20)
    world._fight_adjacent_enemy = Mock()
    world.active_inventory_slot = 1  # Empty hand attacks; a block would place.
    mouse(world, *point(world, 21, 20), curses.BUTTON1_PRESSED)
    world._fight_adjacent_enemy.assert_called_once_with("rat")
    mouse(world, *point(world, 21, 20), curses.BUTTON1_RELEASED)
    _, panel, _ = client.layout_columns(120)
    mouse(world, panel + 3, 7, curses.BUTTON1_PRESSED)
    assert world.active_inventory_slot == 4
    assert world._mouse_target() is None
    world._send.assert_not_called()


def test_wheel_wraps_and_release_does_not_repeat(world):
    mouse(world, 0, 0, curses.BUTTON4_PRESSED)
    assert world.active_inventory_slot == 9
    world.process_key(ord("1"))
    mouse(world, *point(world, 21, 20), curses.BUTTON1_PRESSED)
    world._send.assert_called_once_with({"build": True, "x": 21, "y": 20, "material": "wood"})
    mouse(world, *point(world, 21, 20), curses.BUTTON1_RELEASED)
    assert world._send.call_count == 1


def test_out_of_range_build_and_attack_send_nothing(world):
    for building in (True, False):
        world.building_mode_active = building
        state = curses.BUTTON1_PRESSED
        mouse(world, *point(world, 25, 20), state)
    world._send.assert_not_called()
    assert "reach" in world._notice


def test_build_checks_materials_and_occupied_tiles(world):
    world._prediction_blocked.return_value = True
    world.building_mode_active = True
    mouse(world, *point(world, 21, 20), curses.BUTTON1_PRESSED)
    assert "occupied" in world._notice
    mouse(world, *point(world, 21, 20), curses.BUTTON1_RELEASED)
    world.active_inventory_slot = 1
    client.game_state["enemies"] = {}
    mouse(world, *point(world, 21, 20), curses.BUTTON1_PRESSED)
    # Depleted slots are empty hands and therefore gather, rather than placing
    # a stale zero-count material from the old hard-coded hotbar.
    world._send.assert_called_once_with({"gather": True, "dx": 1, "dy": 0, "tool": None})


class Screen:
    def __init__(self, rows=30, columns=120):
        self.rows, self.columns = rows, columns
        self.keys = deque()
    def getmaxyx(self):
        return self.rows, self.columns
    def addstr(self, *args):
        pass
    def refresh(self):
        pass
    def timeout(self, delay):
        pass
    def getch(self):
        return self.keys.popleft() if self.keys else -1


@pytest.mark.parametrize("size", [(24, 80), (30, 120), (48, 180), (16, 40)])
def test_battle_art_and_hitboxes_follow_visible_cards(size):
    game = prepare_card_battle("enemy_giant_rat")
    game.start_battle()
    game.start_player_turn()
    screen = Screen(*size)
    terminal = CardTerminal(TerminalRenderer(screen))
    terminal.first_frame = False
    with patch.object(curses, "color_pair", return_value=0), use_terminal(terminal):
        GameView().display_board(game.player, game.enemy, game.action_log, selected_index=0)
        assert len(terminal.lines) <= size[0]
        assert all(get_visible_len(line) <= size[1] for line in terminal.lines)
        if size[0] >= 24:
            assert any("▀" in line for line in terminal.lines)
        cards = [target for target in terminal.mouse_targets if isinstance(target[-1], tuple)]
        assert cards
        left, top, right, bottom, action = cards[0]
        assert 0 <= left < right <= size[1] and 0 <= top < bottom <= size[0]
        screen.keys.append(curses.KEY_MOUSE)
        with patch.object(curses, "getmouse", return_value=(0, left, top, 0, curses.BUTTON1_PRESSED)):
            assert terminal.get_key() == action
        PauseMenuView().display(["Resume", "Quit to Menu"], 0, size[1], size[0])
        assert all(target[-1][0] == "pause" for target in terminal.mouse_targets)


def test_resize_invalidates_stale_battle_click_targets():
    screen = Screen()
    screen.keys.append(curses.KEY_RESIZE)
    terminal = CardTerminal(TerminalRenderer(screen))
    terminal.first_frame = False
    terminal.mouse_targets = [(0, 0, 10, 10, b'e')]
    assert terminal.get_key() == b'<RESIZE>'
    assert terminal.mouse_targets == []

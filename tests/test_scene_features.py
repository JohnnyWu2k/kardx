"""Interactive menu, battle reveal, and compressed image regressions."""

import curses
import unittest
from collections import deque
from importlib.resources import files
from io import BytesIO
from unittest.mock import patch

from PIL import Image

from ttx.cli import _menu, menu_layout
from ttx.terminal import CardTerminal, TerminalRenderer
from ttx.world.render import DotCanvas, terrain, tree_sprite
from ttx.world.sprites import load_sprite


class Screen:
    def __init__(self, rows=30, columns=120, keys=()):
        self.rows, self.columns = rows, columns
        self.keys = deque(keys)
        self.cells = {}
        self.writes = []
        self.resize = None

    def getmaxyx(self):
        return self.rows, self.columns

    def timeout(self, _delay):
        pass

    def keypad(self, _enabled):
        pass

    def getch(self):
        key = self.keys.popleft() if self.keys else -1
        if key == curses.KEY_RESIZE and self.resize:
            self.rows, self.columns = self.resize
        return key

    def addstr(self, y, x, text, attr=0):
        assert 0 <= y < self.rows and 0 <= x < self.columns
        self.writes.append((y, x, text, attr))
        for offset, char in enumerate(text):
            if x + offset < self.columns:
                self.cells[y, x + offset] = char, attr

    def refresh(self):
        pass


class MenuTests(unittest.TestCase):
    def test_mouse_clicks_centered_fullscreen_buttons(self):
        for rows, columns in ((30, 120), (55, 210)):
            options = ["Host a game", "Join a game", "Settings", "Quit"]
            title_y, _, buttons = menu_layout(rows, columns, "TTX", options)
            left, y, right, _ = buttons[1]
            self.assertAlmostEqual((left + right) / 2, columns / 2, delta=0.5)
            screen = Screen(rows, columns, [curses.KEY_MOUSE])
            renderer = TerminalRenderer(screen)
            with patch.object(curses, "mousemask") as mask, patch.object(
                curses, "getmouse", return_value=(0, (left + right) // 2, y, 0, curses.BUTTON1_CLICKED)
            ):
                self.assertEqual(_menu(screen, renderer, "TTX", options, "Side-view RPG"), 1)
            self.assertTrue(mask.called)
            self.assertEqual(screen.cells[title_y, (columns - 3) // 2][0], "T")
            self.assertEqual(screen.cells[y, left][1], curses.A_NORMAL)

    def test_outside_click_uses_keyboard_fallback_and_resize_recalculates_hitboxes(self):
        options = ["Fullscreen", "Back"]
        screen = Screen(24, 80, [curses.KEY_MOUSE, curses.KEY_DOWN, 10])
        with patch.object(curses, "mousemask"), patch.object(
            curses, "getmouse", return_value=(0, 0, 0, 0, curses.BUTTON1_CLICKED)
        ):
            self.assertEqual(_menu(screen, TerminalRenderer(screen), "Settings", options), 1)
        screen = Screen(24, 80, [curses.KEY_RESIZE, curses.KEY_MOUSE])
        screen.resize = (48, 200)
        _, _, buttons = menu_layout(48, 200, "Settings", options)
        left, top, _, _ = buttons[0]
        with patch.object(curses, "mousemask"), patch.object(
            curses, "getmouse", return_value=(0, left + 2, top, 0, curses.BUTTON1_PRESSED)
        ), patch("ttx.terminal.time.sleep"):
            self.assertEqual(_menu(screen, TerminalRenderer(screen), "Settings", options), 0)


class BattleRevealTests(unittest.TestCase):
    def test_veil_reaches_bottom_right_and_reverses_over_a_ready_frame(self):
        screen = Screen(12, 28)
        renderer = TerminalRenderer(screen)
        world = renderer.frame()
        for row in range(world.rows):
            world.addstr(row, 0, "w" * world.columns)
        renderer.present(world)
        snapshots = []
        actual_present = renderer.present

        def capture(frame):
            snapshots.append(frame.copy())
            return actual_present(frame)

        with patch.object(renderer, "present", side_effect=capture), patch("ttx.terminal.time.sleep"), patch.object(
            curses, "color_pair", return_value=0
        ):
            renderer.begin_battle_transition()
            self.assertTrue(renderer.battle_transition_active)
            peak = snapshots[-1]
            self.assertTrue(all(char != "w" for row in peak.cells for char, _ in row))
            self.assertTrue(any(char == "*" for row in peak.cells for char, _ in row))
            cycles = [0]

            def ready():
                cycles[0] += 1
                return cycles[0] >= 3

            self.assertTrue(renderer.wait_battle_transition(ready))
            self.assertGreater(len(snapshots), 9)
            battle = renderer.frame()
            for row in range(battle.rows):
                battle.addstr(row, 0, "B" * battle.columns)
            back_start = len(snapshots)
            renderer.complete_battle_transition(battle)
        first_back = snapshots[back_start]
        self.assertNotEqual(first_back.cells[0][0][0], "B")
        self.assertEqual(first_back.cells[-1][-1][0], "B")
        self.assertEqual(renderer.last.cells, battle.cells)
        self.assertFalse(renderer.battle_transition_active)

    def test_first_card_frame_finishes_pending_reveal(self):
        screen = Screen(8, 30)
        renderer = TerminalRenderer(screen)
        renderer.present(renderer.frame())
        with patch("ttx.terminal.time.sleep"), patch.object(curses, "color_pair", return_value=0):
            renderer.begin_battle_transition()
            terminal = CardTerminal(renderer)
            terminal.render(["Battle ready"])
        self.assertFalse(renderer.battle_transition_active)
        self.assertEqual("".join(char for char, _ in renderer.last.cells[0][:12]), "Battle ready")


class PixelArtTests(unittest.TestCase):
    def test_compressed_pngs_are_sharp_and_resource_loader_keeps_tree_and_path(self):
        root = files("ttx").joinpath("assets")
        for filename, expected_size in (("woodland_tree.png", (48, 72)), ("grass_road.png", (32, 16))):
            data = root.joinpath(filename).read_bytes()
            self.assertLess(len(data), 4096)
            with Image.open(BytesIO(data)) as image:
                self.assertEqual(image.size, expected_size)
                self.assertLessEqual(len(image.getcolors(100)), 8)
        with patch.object(curses, "color_pair", side_effect=lambda index: index * 256):
            load_sprite.cache_clear()
            tree, road = load_sprite("tree"), load_sprite("road")
        self.assertEqual((tree.width, tree.height), (12, 24))
        self.assertGreater(sum(visible for row in tree.pixels for visible, _ in row), 100)
        self.assertFalse(tree.pixels[0][0][0])
        self.assertTrue(all(visible for visible, _ in tree.pixels[-1][5:7]))
        self.assertTrue(any(not visible for row in road.pixels for visible, _ in row))
        self.assertTrue(any(attr == 3 * 256 | curses.A_BOLD for row in road.pixels for visible, attr in row if visible))

    def test_map_renders_path_and_tree_from_png_and_respects_mining_override(self):
        class TinyMap:
            AIR = "."

            def get_tile(self, x, y):
                return '"' if 2 <= x <= 3 and y == 2 else self.AIR

        with patch.object(curses, "color_pair", side_effect=lambda index: index * 256):
            load_sprite.cache_clear()
            canvas = DotCanvas(8, 12)
            terrain(canvas, TinyMap(), (0, 0), {}, {'"': 0})
            road_cells = [canvas.cells[2][x][0] for x in range(4, 8)]
            self.assertTrue(any(mask != 255 for mask in road_cells))
            mined = DotCanvas(8, 12)
            terrain(mined, TinyMap(), (0, 0), {"2,2": {"char": "."}}, {'"': 0})
            self.assertEqual([mined.cells[2][x][0] for x in range(4, 6)], [0, 0])
            tree_sprite(canvas, {"x": 4, "y": 5}, (0, 0), 0)
            self.assertTrue(any(canvas.cells[y][x][0] for y in range(2, 6) for x in range(5, 11)))


if __name__ == "__main__":
    unittest.main()

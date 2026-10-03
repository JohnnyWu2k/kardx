import curses
import io
import unittest
from unittest.mock import Mock, patch

from kardx import keyboard, view_utils
from kardx.scenes.pause_menu.pause_menu_view import PauseMenuView
from ttx.cli import maximize_terminal
from ttx.combat.card_battle import GameController, run_card_battle
from ttx.input import MotionInput, windows_key_state
from ttx.terminal import CardTerminal, Frame, TerminalRenderer


def window_api(class_name="CASCADIA_HOSTING_WINDOW_CLASS"):
    api = Mock()
    api.GetConsoleWindow.return_value = 7
    api.GetAncestor.return_value = 42
    api.GetForegroundWindow.return_value = 42

    def copy_class(_window, buffer, _size):
        buffer.value = class_name
        return len(class_name)

    api.GetClassNameW.side_effect = copy_class
    return api


class RecordingScreen:
    def __init__(self, rows=24, columns=80, keys=()):
        self.rows, self.columns = rows, columns
        self.cells = {}
        self.writes = []
        self.refreshes = 0
        self.keys = iter(keys)
        self.timeouts = []

    def getmaxyx(self):
        return self.rows, self.columns

    def addstr(self, y, x, text, attr=0):
        self.writes.append((y, x, text, attr))
        if not (0 <= y < self.rows and 0 <= x < self.columns):
            raise AssertionError("out-of-bounds terminal write")
        for offset, char in enumerate(text):
            self.cells[y, x + offset] = (char, attr)

    def refresh(self):
        self.refreshes += 1

    def timeout(self, delay):
        self.timeouts.append(delay)

    def getch(self):
        return next(self.keys, -1)


class MotionInputTests(unittest.TestCase):
    def test_native_hold_release_chords_and_jump_edges(self):
        state = [1, False]
        controls = MotionInput(lambda: tuple(state))
        self.assertEqual(controls.sample(0), (1, False))
        self.assertEqual(controls.sample(2), (1, False))
        state[:] = [1, True]
        self.assertEqual(controls.sample(2.1), (1, True))
        self.assertEqual(controls.sample(2.2), (1, False))
        state[:] = [-1, False]
        self.assertEqual(controls.sample(2.3), (-1, False))
        state[:] = [0, False]
        self.assertEqual(controls.sample(2.4), (0, False))

    def test_native_short_jump_tap_is_not_lost_and_reset_suppresses_held_jump(self):
        state = [0, False]
        controls = MotionInput(lambda: tuple(state))
        controls.feed("w", 1.0)
        self.assertEqual(controls.sample(1.1), (0, True))
        state[:] = [0, True]
        controls.reset()
        self.assertEqual(controls.sample(1.2), (0, False))
        state[:] = [0, False]
        controls.sample(1.3)
        state[:] = [0, True]
        self.assertEqual(controls.sample(1.4), (0, True))

    def test_native_short_walk_tap_is_visible_but_release_overrides_repeat(self):
        state = [0, False]
        controls = MotionInput(lambda: tuple(state))
        controls.feed("d", 1.0)
        self.assertEqual(controls.sample(1.01), (1, False))
        self.assertEqual(controls.sample(1.04), (1, False))
        self.assertEqual(controls.sample(1.09), (0, False))
        state[:] = [-1, False]
        controls.sample(1.1)
        controls.feed("a", 1.11)
        state[:] = [0, False]
        self.assertEqual(controls.sample(1.12), (0, False))
        self.assertEqual(controls.sample(1.14), (0, False))

    def test_repeat_fallback_combines_walking_and_jumping_then_releases(self):
        controls = MotionInput()
        controls.feed("a", 1.0)
        controls.feed("w", 1.0)
        self.assertEqual(controls.sample(1.05), (-1, True))
        self.assertEqual(controls.sample(1.10), (-1, False))
        controls.feed("w", 1.10)
        self.assertEqual(controls.sample(1.12), (-1, False))
        self.assertEqual(controls.sample(1.3), (0, False))
        controls.feed("d", 1.4)
        controls.reset()
        self.assertEqual(controls.sample(1.45), (0, False))

    def test_windows_polling_uses_down_bit_and_stops_when_unfocused(self):
        api = window_api()
        api.GetAsyncKeyState.side_effect = lambda key: 0x8000 if key in (0x44, 0x20) else 1
        with patch("ttx.input.os.name", "nt"), patch("ttx.input.sys.stdin") as stdin, patch(
            "ttx.input.ctypes.WinDLL", return_value=api, create=True
        ):
            stdin.isatty.return_value = True
            sample = windows_key_state()
            self.assertEqual(sample(), (1, True))
            api.GetAsyncKeyState.side_effect = lambda key: 0x8000 if key in (0x41, 0x44) else 0
            controls = MotionInput(sample)
            controls.feed("d", 1.0)
            self.assertEqual(controls.sample(1.01), (0, False))
            api.GetForegroundWindow.return_value = 100
            self.assertEqual(sample(), (0, False))
            controls = MotionInput(sample)
            controls.feed("d", 1.0)
            controls.feed("w", 1.0)
            self.assertEqual(controls.sample(1.01), (0, False))
            api.GetForegroundWindow.return_value = 42
            api.GetAsyncKeyState.side_effect = lambda key: 0
            self.assertEqual(controls.sample(1.02), (0, False))

    def test_windows_polling_uses_own_console_when_another_window_is_initially_focused(self):
        api = window_api()
        api.GetForegroundWindow.return_value = 100
        api.GetAsyncKeyState.return_value = 0x8000
        with patch("ttx.input.os.name", "nt"), patch("ttx.input.sys.stdin") as stdin, patch(
            "ttx.input.ctypes.WinDLL", return_value=api, create=True
        ):
            stdin.isatty.return_value = True
            sample = windows_key_state()
            self.assertEqual(sample(), (0, False))
            api.GetAsyncKeyState.assert_not_called()
            api.GetForegroundWindow.return_value = 42
            self.assertTrue(sample()[1])

    def test_unknown_console_host_uses_repeat_fallback(self):
        api = window_api("PseudoConsoleWindow")
        with patch("ttx.input.os.name", "nt"), patch("ttx.input.sys.stdin") as stdin, patch(
            "ttx.input.ctypes.WinDLL", return_value=api, create=True
        ):
            stdin.isatty.return_value = True
            self.assertIsNone(windows_key_state())
            api.GetAsyncKeyState.assert_not_called()


class WindowTests(unittest.TestCase):
    def test_maximize_targets_own_terminal_instead_of_foreground_window(self):
        for class_name in ("ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS"):
            api = window_api(class_name)
            api.GetForegroundWindow.return_value = 100
            with self.subTest(host=class_name), patch("ttx.cli.sys.platform", "win32"), patch(
                "ttx.cli.sys.stdin"
            ) as stdin, patch("ttx.input.ctypes.WinDLL", return_value=api, create=True), patch(
                "ttx.cli.time.sleep"
            ), patch("ttx.cli.curses.update_lines_cols", create=True):
                stdin.isatty.return_value = True
                maximize_terminal()
                api.ShowWindow.assert_called_once_with(42, 3)
                api.GetForegroundWindow.assert_not_called()

    def test_maximize_skips_unknown_absent_or_noninteractive_console(self):
        for class_name, console, is_tty in (("PseudoConsoleWindow", 7, True),
                                             ("ConsoleWindowClass", 0, True),
                                             ("ConsoleWindowClass", 7, False)):
            api = window_api(class_name)
            api.GetConsoleWindow.return_value = console
            with self.subTest(host=class_name, console=console, tty=is_tty), patch(
                "ttx.cli.sys.platform", "win32"
            ), patch("ttx.cli.sys.stdin") as stdin, patch(
                "ttx.input.ctypes.WinDLL", return_value=api, create=True
            ):
                stdin.isatty.return_value = is_tty
                maximize_terminal()
                api.ShowWindow.assert_not_called()


class TerminalTests(unittest.TestCase):
    def test_unchanged_frames_write_nothing_and_motion_erases_old_cell(self):
        screen = RecordingScreen(rows=4, columns=20)
        renderer = TerminalRenderer(screen)
        frame = renderer.frame()
        frame.addstr(2, 4, "@")
        renderer.present(frame)
        screen.writes.clear()
        refreshes = screen.refreshes
        self.assertFalse(renderer.present(frame))
        self.assertEqual(screen.writes, [])
        self.assertEqual(screen.refreshes, refreshes)
        next_frame = renderer.frame()
        next_frame.addstr(2, 5, "@")
        renderer.present(next_frame)
        self.assertEqual(screen.cells[2, 4][0], " ")
        self.assertEqual(screen.cells[2, 5][0], "@")
        self.assertEqual(sum(len(call[2]) for call in screen.writes), 2)

    def test_resize_repaints_and_color_changes_are_not_skipped(self):
        screen = RecordingScreen(rows=2, columns=8)
        renderer = TerminalRenderer(screen)
        frame = renderer.frame()
        frame.addstr(0, 0, "text")
        renderer.present(frame)
        changed = frame.copy()
        changed.addstr(0, 0, "text", curses.A_BOLD)
        screen.writes.clear()
        renderer.present(changed)
        self.assertTrue(screen.writes)
        self.assertEqual(screen.cells[0, 0][1], curses.A_BOLD)
        screen.rows, screen.columns = 1, 1
        renderer.present(renderer.frame())
        self.assertEqual(renderer.last.getmaxyx(), (1, 1))

    def test_transition_keeps_existing_content_until_rows_are_revealed(self):
        screen = RecordingScreen(rows=8, columns=12)
        renderer = TerminalRenderer(screen)
        before, after = renderer.frame(), renderer.frame()
        for row in range(8):
            before.addstr(row, 0, "world")
            after.addstr(row, 0, "battle")
        renderer.present(before)
        snapshots = []
        original = renderer.present

        def record(frame):
            snapshots.append(frame.copy())
            return original(frame)

        with patch.object(renderer, "present", side_effect=record), patch("ttx.terminal.time.sleep"):
            renderer.transition(after)
        self.assertEqual(snapshots[0].cells[0], before.cells[0])
        self.assertEqual(snapshots[0].cells[3], after.cells[3])
        self.assertEqual(snapshots[-1].cells, after.cells)

    def test_frame_fits_wide_text_and_translates_ansi_colors(self):
        frame = Frame(2, 6)
        with patch("ttx.terminal.curses.color_pair", return_value=256):
            frame.addstr(0, 0, "\033[91m敵人\033[0mX")
        self.assertEqual([char for char, _ in frame.cells[0]], ["敵", "", "人", "", "X", " "])
        self.assertNotEqual(frame.cells[0][0][1], 0)
        self.assertEqual(frame.cells[0][4][1], 0)
        frame.addstr(1, 5, "敵")
        self.assertEqual(frame.cells[1][5][0], " ")

    def test_card_battle_uses_curses_for_render_keys_and_pause_overlay(self):
        screen = RecordingScreen(keys=[curses.KEY_LEFT, ord("E")])
        renderer = TerminalRenderer(screen)
        renderer.present(renderer.frame())
        terminal = CardTerminal(renderer)

        def play(controller):
            controller.game.start_battle()
            controller.view.display_board(controller.game.player, controller.game.enemy, controller.game.action_log)
            self.assertEqual(keyboard.get_key(), keyboard.KEY_LEFT)
            self.assertEqual(keyboard.get_key_non_blocking(), keyboard.KEY_E)
            PauseMenuView().display(["Resume", "Quit to Menu"], 0, 80, 24)
            return "victory"

        output = io.StringIO()
        with patch.object(GameController, "run", play), patch("ttx.terminal.time.sleep"), patch(
            "ttx.terminal.curses.color_pair", return_value=0
        ), patch("sys.stdout", output):
            result = run_card_battle("enemy_giant_rat", terminal=terminal)
        self.assertTrue(result.victory)
        self.assertTrue(result.deck_ids)
        self.assertEqual(output.getvalue(), "")
        self.assertIsNone(keyboard._key_readers.get())
        self.assertIsNone(view_utils._terminal.get())

    def test_ansi_renderer_updates_changed_rows_and_restores_overlay(self):
        output = io.StringIO()
        with patch("sys.stdout", output), patch.object(view_utils, "terminal_size", return_value=(20, 4)):
            view_utils.render_screen(["HP: 50", "cards"])
            self.assertNotIn("\033[J", output.getvalue())
            self.assertNotIn("\n", output.getvalue())
            output.seek(0)
            output.truncate(0)
            view_utils.render_screen(["HP: 50", "cards"])
            self.assertEqual(output.getvalue(), "")
            view_utils.render_screen(["HP: 49", "cards"])
            self.assertIn("HP: 49", output.getvalue())
            self.assertNotIn("cards", output.getvalue())
            view_utils.render_overlay(["paused"], 2, 1)
            output.seek(0)
            output.truncate(0)
            view_utils.render_screen(["HP: 49", "cards"])
            self.assertIn("cards", output.getvalue())

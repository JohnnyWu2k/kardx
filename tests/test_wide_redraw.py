"""Model terminal hosts that advance one cell for a double-width character."""
import curses
from unittest.mock import Mock, patch

from wcwidth import wcswidth

from ttx.cli import name_world, show_progress
from ttx.terminal import Frame, TerminalRenderer


class SingleAdvanceScreen:
    def __init__(self):
        self.cells = [[" "] * 80 for _ in range(24)]
        self.cursor = (0, 0)
        self.clears = 0
        self.redraws = []
        self.get_wch = Mock(side_effect=["測", "試", "世", "界", "\n"])

    def getmaxyx(self):
        return 24, 80

    def addstr(self, y, x, text, attr=0):
        for char in text:
            if x < 80:
                self.cells[y][x] = char
                if wcswidth(char) == 2 and x + 1 < 80:
                    self.cells[y][x + 1] = ""
            x += 1  # Deliberately emulate the problematic host advance.

    def move(self, y, x):
        self.cursor = y, x

    def clrtoeol(self):
        y, x = self.cursor
        self.cells[y][x:] = [" "] * (80 - x)

    def redrawln(self, y, count):
        self.redraws.append((y, count))

    def erase(self):
        self.cells = [[" "] * 80 for _ in range(24)]
        self.clears += 1

    def clearok(self, value):
        pass

    def refresh(self):
        pass


def test_cjk_glyphs_and_following_text_use_explicit_display_columns():
    screen = SingleAdvanceScreen()
    renderer = TerminalRenderer(screen)
    frame = Frame(24, 80)
    frame.addstr(4, 8, "測試世界_A")
    renderer.present(frame)
    assert screen.cells[4][8:18] == ["測", "", "試", "", "世", "", "界", "", "_", "A"]
    renderer.present(Frame(24, 80))
    assert not any(char in "測試世界" for row in screen.cells for char in row if char)
    assert (4, 1) in screen.redraws


def test_unicode_world_name_cannot_leak_into_loading_or_world_frames():
    screen = SingleAdvanceScreen()
    renderer = TerminalRenderer(screen)
    with patch.object(curses, "noecho") as noecho:
        assert name_world(screen, renderer) == "測試世界"
    noecho.assert_called()
    # IME/external echo can be outside the logical frame's tracked text.
    screen.cells[8][60] = "試"
    assert renderer._force_redraw
    with patch("ttx.cli.time.sleep"):
        show_progress(screen, renderer=renderer)
    assert screen.clears == 1
    assert all(char not in "測試世界" for row in screen.cells for char in row if char)
    renderer.present(Frame(24, 80))
    assert all(char == " " for row in screen.cells for char in row)


def test_no_wide_redraw_is_added_to_ordinary_game_motion():
    screen = SingleAdvanceScreen()
    renderer = TerminalRenderer(screen)
    frame = Frame(24, 80)
    frame.addstr(2, 4, "@")
    renderer.present(frame)
    frame.addstr(2, 4, " @")
    renderer.present(frame)
    assert screen.clears == 0 and not screen.redraws


def test_startup_status_does_not_add_a_second_scene_animation():
    screen = SingleAdvanceScreen()
    renderer = TerminalRenderer(screen)
    renderer.present(Frame(24, 80))
    with patch.object(renderer, "transition") as transition, patch("ttx.cli.time.sleep"):
        show_progress(screen, renderer=renderer)
    transition.assert_not_called()

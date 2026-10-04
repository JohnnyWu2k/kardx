"""Compose complete frames in memory and send only changed runs to curses."""

from __future__ import annotations

import curses
import re
import time

from wcwidth import wcwidth, wcswidth
from kardx.settings import settings_manager

SGR = re.compile(r"\033\[([0-9;]*)m")
COLOR_PAIRS = {31: 5, 32: 2, 33: 7, 34: 8, 35: 9, 36: 4, 37: 3}
BATTLE_STEPS = 9


class Frame:
    def __init__(self, rows: int, columns: int):
        self.rows, self.columns = max(0, rows), max(0, columns)
        self.cells = [[(" ", 0) for _ in range(self.columns)] for _ in range(self.rows)]

    def getmaxyx(self) -> tuple[int, int]:
        return self.rows, self.columns

    def copy(self) -> Frame:
        frame = Frame(self.rows, self.columns)
        frame.cells = [row.copy() for row in self.cells]
        return frame

    def addch(self, y: int, x: int, char: str, attr: int = 0):
        width = wcwidth(char) if len(char) == 1 else wcswidth(char)
        if not (0 <= y < self.rows and 0 <= x and width in (1, 2) and x + width <= self.columns):
            return
        row = self.cells[y]
        for column in range(x, x + width):
            old_char = row[column][0]
            if old_char == "" and column > 0:
                row[column - 1] = (" ", 0)
            elif old_char != " " and wcswidth(old_char) == 2 and column + 1 < self.columns:
                row[column + 1] = (" ", 0)
            row[column] = (" ", 0)
        row[x] = (char, attr)
        if width == 2:
            row[x + 1] = ("", attr)

    def addstr(self, y: int, x: int, text: str, attr: int = 0):
        if not 0 <= y < self.rows:
            return
        index = 0
        foreground, background = 7, None
        while index < len(text):
            match = SGR.match(text, index)
            if match:
                for code in (int(code or "0") for code in match.group(1).split(";")):
                    if code == 0:
                        attr = 0
                        foreground, background = 7, None
                    elif code == 1:
                        attr |= curses.A_BOLD
                    elif code == 2:
                        attr |= curses.A_DIM
                    elif code == 7:
                        attr |= curses.A_REVERSE
                    elif code == 22:
                        attr &= ~(curses.A_BOLD | curses.A_DIM)
                    elif code == 39:
                        attr &= ~curses.A_COLOR
                    elif 30 <= code <= 37 or 90 <= code <= 97:
                        base = code - 60 if code >= 90 else code
                        foreground = base - 30
                        pair = COLOR_PAIRS.get(base, 3) if background is None else 16 + foreground * 8 + background
                        attr = (attr & ~curses.A_COLOR) | curses.color_pair(pair)
                        if code >= 90:
                            attr |= curses.A_BOLD
                    elif 40 <= code <= 47:
                        background = code - 40
                        attr = (attr & ~curses.A_COLOR) | curses.color_pair(16 + foreground * 8 + background)
                index = match.end()
                continue
            char = text[index]
            width = wcwidth(char)
            if width == 0 and 0 < x <= self.columns:
                previous, previous_attr = self.cells[y][x - 1]
                # A continuation cell belongs to the wide character before it.
                column = x - 2 if previous == "" and x > 1 else x - 1
                previous, previous_attr = self.cells[y][column]
                self.cells[y][column] = (previous + char, previous_attr)
            elif width > 0:
                if x >= self.columns:
                    break
                if x >= 0 and x + width <= self.columns:
                    self.addch(y, x, char, attr)
                x += width
            index += 1


class TerminalRenderer:
    def __init__(self, screen):
        self.screen = screen
        self.last: Frame | None = None
        self._battle_source: Frame | None = None
        self._force_redraw = False
        # Finish a composed frame even while motion reports are arriving.
        try:
            curses.typeahead(-1)
        except curses.error:
            pass
        if hasattr(screen, "leaveok"):
            screen.leaveok(True)
        if hasattr(screen, "scrollok"):
            screen.scrollok(False)

    def frame(self) -> Frame:
        return Frame(*self.screen.getmaxyx())

    def invalidate(self):
        """Discard text-entry/IME residue in curses' physical-screen cache."""
        self.last = None
        self._force_redraw = True

    def present(self, frame: Frame) -> bool:
        previous = self.last
        if previous and previous.getmaxyx() != frame.getmaxyx():
            previous = None
            self._force_redraw = True
        if self._force_redraw:
            if hasattr(self.screen, "erase"):
                self.screen.erase()
            if hasattr(self.screen, "clearok"):
                self.screen.clearok(True)
            previous = None
            self._force_redraw = False
        changed = False
        for y, row in enumerate(frame.cells):
            old_row = previous.cells[y] if previous else None
            if old_row and row != old_row and any(char == "" for char, _ in old_row):
                # PDCurses and terminal hosts can disagree on CJK cell width.
                # Clear the entire old line, not just the tracked leading cell.
                if hasattr(self.screen, "move") and hasattr(self.screen, "clrtoeol"):
                    self.screen.move(y, 0)
                    self.screen.clrtoeol()
                if hasattr(self.screen, "redrawln"):
                    self.screen.redrawln(y, 1)
                old_row = None
            x = 0
            while x < frame.columns:
                if old_row and row[x] == old_row[x]:
                    x += 1
                    continue
                start = x
                # Repaint the leading cell if a changed continuation is found.
                if row[x][0] == "" and x > 0:
                    start = x - 1
                attr = row[start][1]
                x = max(x + 1, start + 1)
                wide = wcswidth(row[start][0]) == 2
                if wide:
                    x = start + 2
                while not wide and x < frame.columns and row[x][1] == attr:
                    if wcswidth(row[x][0]) == 2 or (row[x][0] and old_row and row[x] == old_row[x]):
                        break
                    x += 1
                text = "".join(cell[0] for cell in row[start:x])
                try:
                    self.screen.addstr(y, start, text, attr)
                except curses.error:
                    # Some curses implementations report ERR after writing the
                    # lower-right cell, even when scrolling is disabled.
                    pass
                changed = True
        self.last = frame.copy()
        if changed:
            if hasattr(self.screen, "noutrefresh"):
                self.screen.noutrefresh()
                curses.doupdate()
            else:
                self.screen.refresh()
        return changed

    def transition(self, frame: Frame, duration: float = 0.16):
        previous = self.last
        if not previous or previous.getmaxyx() != frame.getmaxyx():
            self.present(frame)
            return
        # Reveal the incoming scene from the center without an empty frame.
        steps = 4
        started = time.monotonic()
        for step in range(1, steps + 1):
            mixed = previous.copy()
            margin = round(frame.rows * (1 - step / steps) / 2)
            for row in range(margin, frame.rows - margin):
                mixed.cells[row] = frame.cells[row].copy()
            self.present(mixed)
            if step < steps:
                time.sleep(max(0, started + duration * step / (steps - 1) - time.monotonic()))

    @property
    def battle_transition_active(self) -> bool:
        return self._battle_source is not None

    def _battle_veil(self, base: Frame, progress: float, pulse: int) -> Frame:
        frame = base.copy()
        if progress <= 0:
            return frame
        width, height = max(1, frame.columns - 1), max(1, frame.rows - 1)
        pair = {"magenta": 9, "cyan": 4, "blue": 8, "green": 2, "gold": 7, "red": 5, "white": 3}
        color = curses.color_pair(pair.get(settings_manager.get("battle_particle_color"), 9))
        for y in range(frame.rows):
            for x in range(frame.columns):
                diagonal = (x / width + y / height) / 2
                if diagonal > progress:
                    continue
                sparkle = (abs(diagonal - progress) < 0.055 and (x * 7 + y * 11 + pulse) % 9 == 0)
                sparkle |= (progress >= 1 and (x * 13 + y * 17 + pulse * 5) % 73 == 0)
                symbol = "*" if sparkle else ("▒" if (x + y) % 2 else "░")
                attribute = color | (curses.A_BOLD if sparkle else curses.A_DIM)
                frame.addch(y, x, symbol, attribute)
        return frame

    def begin_battle_transition(self, duration: float | None = None):
        duration = settings_manager.get("battle_transition_duration", 0.6) / 2 if duration is None else duration
        source = self.last if self.last and self.last.getmaxyx() == self.screen.getmaxyx() else self.frame()
        self._battle_source = source.copy()
        if duration <= 0:
            return
        started = time.monotonic()
        for step in range(1, BATTLE_STEPS + 1):
            self.present(self._battle_veil(self._battle_source, step / BATTLE_STEPS, step))
            time.sleep(max(0, started + duration * step / BATTLE_STEPS - time.monotonic()))

    def wait_battle_transition(self, ready, timeout: float | None = None) -> bool:
        """Keep the covered scene alive while data or images finish loading."""
        deadline = None if timeout is None else time.monotonic() + timeout
        pulse = 0
        while not ready():
            if deadline is not None and time.monotonic() >= deadline:
                return False
            source = self._battle_source
            if source is None:
                return ready()
            if settings_manager.get("battle_transition_duration", 0.6) > 0:
                self.present(self._battle_veil(source, 1.0, pulse))
            pulse += 1
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())) if deadline is not None else 0.05)
        return True

    def complete_battle_transition(self, target: Frame, duration: float | None = None):
        duration = settings_manager.get("battle_transition_duration", 0.6) / 2 if duration is None else duration
        source = self._battle_source
        self._battle_source = None
        if duration <= 0:
            self.present(target)
            return
        if source is None or source.getmaxyx() != target.getmaxyx():
            self.transition(target)
            return
        started = time.monotonic()
        for step in range(1, BATTLE_STEPS + 1):
            self.present(self._battle_veil(target, 1 - step / BATTLE_STEPS, step))
            time.sleep(max(0, started + duration * step / BATTLE_STEPS - time.monotonic()))


class CardTerminal:
    """Adapt Kardx's existing view and key interface to the same curses screen."""

    def __init__(self, renderer: TerminalRenderer, on_pause=None, stop_event=None):
        self.renderer = renderer
        self.first_frame = True
        self.lines: list[str] = []
        self.on_pause = on_pause
        self.stop_event = stop_event
        self.mouse_targets = []

    def pause(self, paused: bool):
        if self.on_pause:
            self.on_pause(paused)

    def size(self) -> tuple[int, int]:
        rows, columns = self.renderer.screen.getmaxyx()
        return max(1, columns), max(1, rows)

    def render(self, lines: list[str]):
        self.lines = lines
        frame = self.renderer.frame()
        for row, line in enumerate(lines[:frame.rows]):
            frame.addstr(row, 0, line)
        if self.first_frame:
            if self.renderer.battle_transition_active:
                self.renderer.complete_battle_transition(frame)
            else:
                self.renderer.transition(frame)
            self.first_frame = False
        else:
            self.renderer.present(frame)

    def overlay(self, lines: list[str], x: int, y: int):
        if self.renderer.last and self.renderer.last.getmaxyx() != self.renderer.screen.getmaxyx():
            self.render(self.lines)
        frame = self.renderer.last.copy() if self.renderer.last else self.renderer.frame()
        for row, line in enumerate(lines):
            frame.addstr(y + row, x, line)
        self.renderer.present(frame)

    def _read_key(self, blocking: bool):
        from kardx import keyboard

        screen = self.renderer.screen
        screen.timeout(50 if blocking else 0)
        while True:
            if self.stop_event is not None and self.stop_event.is_set():
                raise ConnectionError("Disconnected from server.")
            key = screen.getch()
            if key == curses.KEY_RESIZE:
                self.mouse_targets = []
                self.render(self.lines)
                return b'<RESIZE>'
            if key == curses.KEY_MOUSE:
                from ttx.mouse import button, wheel
                try:
                    _, x, y, _, state = curses.getmouse()
                except curses.error:
                    continue
                scroll = wheel(state)
                if scroll:
                    return keyboard.KEY_LEFT if scroll < 0 else keyboard.KEY_RIGHT
                if button(state):
                    for left, top, right, bottom, action in self.mouse_targets:
                        if left <= x < right and top <= y < bottom:
                            return action
                if not blocking:
                    return None
                continue
            if key == -1:
                if blocking:
                    continue
                return None
            special = {curses.KEY_UP: keyboard.KEY_UP, curses.KEY_DOWN: keyboard.KEY_DOWN,
                       curses.KEY_LEFT: keyboard.KEY_LEFT, curses.KEY_RIGHT: keyboard.KEY_RIGHT,
                       10: keyboard.KEY_ENTER, 13: keyboard.KEY_ENTER,
                       curses.KEY_ENTER: keyboard.KEY_ENTER, 27: keyboard.KEY_ESC}
            if key in special:
                return special[key]
            if 0 <= key < 256:
                return bytes([key]).lower()
            if not blocking:
                return None

    def get_key(self):
        return self._read_key(True)

    def get_key_non_blocking(self):
        return self._read_key(False)

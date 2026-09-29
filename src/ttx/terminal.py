"""Compose complete frames in memory and send only changed runs to curses."""

from __future__ import annotations

import curses
import re
import time

from wcwidth import wcwidth

SGR = re.compile(r"\033\[([0-9;]*)m")
COLOR_PAIRS = {31: 5, 32: 2, 33: 7, 34: 8, 35: 9, 36: 4, 37: 3}


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
        if 0 <= y < self.rows and 0 <= x < self.columns:
            self.cells[y][x] = (char, attr)

    def addstr(self, y: int, x: int, text: str, attr: int = 0):
        if not 0 <= y < self.rows:
            return
        index = 0
        while index < len(text):
            match = SGR.match(text, index)
            if match:
                for code in map(int, match.group(1).split(";") if match.group(1) else ["0"]):
                    if code == 0:
                        attr = 0
                    elif code == 1:
                        attr |= curses.A_BOLD
                    elif code == 2:
                        attr |= curses.A_DIM
                    elif code == 7:
                        attr |= curses.A_REVERSE
                    elif code == 22:
                        attr &= ~(curses.A_BOLD | curses.A_DIM)
                    elif 30 <= code <= 37 or 90 <= code <= 97:
                        base = code - 60 if code >= 90 else code
                        attr = (attr & ~curses.A_COLOR) | curses.color_pair(COLOR_PAIRS.get(base, 3))
                        if code >= 90:
                            attr |= curses.A_BOLD
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
                    for offset in range(1, width):
                        self.addch(y, x + offset, "", attr)
                x += width
            index += 1


class TerminalRenderer:
    def __init__(self, screen):
        self.screen = screen
        self.last: Frame | None = None

    def frame(self) -> Frame:
        return Frame(*self.screen.getmaxyx())

    def present(self, frame: Frame) -> bool:
        previous = self.last
        if previous and previous.getmaxyx() != frame.getmaxyx():
            previous = None
        changed = False
        for y, row in enumerate(frame.cells):
            x = 0
            while x < frame.columns:
                if previous and row[x] == previous.cells[y][x]:
                    x += 1
                    continue
                start = x
                # Repaint the leading cell if a changed continuation is found.
                if row[x][0] == "" and x > 0:
                    start = x - 1
                attr = row[start][1]
                x = max(x + 1, start + 1)
                while x < frame.columns and row[x][1] == attr:
                    if row[x][0] and previous and row[x] == previous.cells[y][x]:
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


class CardTerminal:
    """Adapt Kardx's existing view and key interface to the same curses screen."""

    def __init__(self, renderer: TerminalRenderer, on_pause=None):
        self.renderer = renderer
        self.first_frame = True
        self.lines: list[str] = []
        self.on_pause = on_pause

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
            key = screen.getch()
            if key == curses.KEY_RESIZE:
                self.render(self.lines)
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

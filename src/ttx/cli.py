import argparse
import curses
import sys
import time

from ttx import __version__
from ttx.input import terminal_window
from ttx.net.client import init_colors, run_client
from ttx.net.server import PORT, start_server
from ttx.terminal import TerminalRenderer


def menu_layout(rows: int, columns: int, title: str, options: list[str], subtitle: str = ""):
    """Center a menu and return its clickable button rectangles."""
    button_width = min(columns, max(16, max((len(option) for option in options), default=0) + 8))
    button_start = max(0, (columns - button_width) // 2)
    title_y = max(0, (rows - (4 + len(options) * 2)) // 2)
    buttons = [(button_start, title_y + 4 + index * 2,
                button_start + button_width, title_y + 5 + index * 2)
               for index in range(len(options))]
    return title_y, button_width, buttons


def _mouse_choice(buttons):
    try:
        _, x, y, _, state = curses.getmouse()
    except curses.error:
        return None
    pressed = (curses.BUTTON1_CLICKED | curses.BUTTON1_DOUBLE_CLICKED | curses.BUTTON1_PRESSED)
    if not state & pressed:
        return None
    return next((index for index, (left, top, right, bottom) in enumerate(buttons)
                 if left <= x < right and top <= y < bottom), None)


def _menu(stdscr, renderer, title: str, options: list[str], subtitle: str = "") -> int:
    stdscr.timeout(-1)
    stdscr.keypad(True)
    curses.mousemask(curses.BUTTON1_CLICKED | curses.BUTTON1_DOUBLE_CLICKED | curses.BUTTON1_PRESSED)
    selected = 0
    entering = True
    while True:
        frame = renderer.frame()
        title_y, button_width, buttons = menu_layout(frame.rows, frame.columns, title, options, subtitle)
        frame.addstr(title_y, max(0, (frame.columns - len(title)) // 2), title, curses.A_BOLD)
        frame.addstr(title_y + 2, max(0, (frame.columns - len(subtitle)) // 2), subtitle)
        for index, option in enumerate(options):
            left, top, _, _ = buttons[index]
            label = ("[ " + option.center(max(0, button_width - 4)) + " ]") if button_width >= 4 else option
            frame.addstr(top, left, label[:button_width],
                         curses.A_REVERSE if index == selected else curses.A_NORMAL)
        if entering:
            renderer.transition(frame)
            entering = False
        else:
            renderer.present(frame)
        key = stdscr.getch()
        if key == curses.KEY_MOUSE:
            clicked = _mouse_choice(buttons)
            if clicked is not None:
                return clicked
        if key in (curses.KEY_UP, ord("w")):
            selected = max(0, selected - 1)
        elif key in (curses.KEY_DOWN, ord("s")):
            selected = min(len(options) - 1, selected + 1)
        elif key in [curses.KEY_ENTER, 10, 13]:
            return selected
        elif key == 27:
            return len(options) - 1


def main_menu(stdscr, renderer=None) -> str:
    curses.curs_set(0)
    renderer = renderer or TerminalRenderer(stdscr)
    index = _menu(stdscr, renderer, "Kard-X Sandbox", ["Host a game", "Join a game", "Settings", "Quit"],
                  "Side-view sandbox RPG with Kard-X card battles")
    return ["host", "join", "settings", "quit"][index]


def get_server_ip(stdscr, renderer=None) -> str:
    renderer = renderer or TerminalRenderer(stdscr)
    frame = renderer.frame()
    prompt = "Enter server IP (default 127.0.0.1):"
    frame.addstr(max(0, frame.rows // 2 - 2), max(0, (frame.columns - len(prompt)) // 2), prompt)
    renderer.transition(frame)
    stdscr.timeout(-1)
    curses.mousemask(0)
    curses.echo()
    try:
        rows, columns = stdscr.getmaxyx()
        input_width = max(1, min(40, columns - 2))
        ip = stdscr.getstr(min(rows - 1, max(0, rows // 2)),
                           max(0, (columns - input_width) // 2), input_width)
        return ip.decode("utf-8").strip() or "127.0.0.1"
    finally:
        curses.noecho()
        renderer.last = None  # Echoed input bypasses the frame cache.


def show_progress(stdscr, message: str = "Starting server...", duration: float = 0.1, renderer=None):
    renderer = renderer or TerminalRenderer(stdscr)
    frame = renderer.frame()
    frame.addstr(max(0, frame.rows // 2 - 1), max(0, (frame.columns - len(message)) // 2), message)
    renderer.transition(frame)
    time.sleep(duration)


def settings_menu(stdscr, renderer=None):
    renderer = renderer or TerminalRenderer(stdscr)
    while _menu(stdscr, renderer, "Settings", ["Fullscreen", "Back"]) == 0:
        maximize_terminal(stdscr)


def maximize_terminal(stdscr=None):
    if sys.platform != "win32" or not sys.stdin.isatty():
        return
    try:
        import ctypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        hwnd = terminal_window(user32, kernel32)
    except (ImportError, AttributeError, OSError):
        return
    if not hwnd:
        return

    sw_maximize = 3
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.ShowWindow(hwnd, sw_maximize)
    time.sleep(0.15)
    try:
        curses.update_lines_cols()
    except (AttributeError, curses.error):
        pass


def curses_main(stdscr):
    init_colors()
    if hasattr(curses, "set_escdelay"):
        curses.set_escdelay(25)
    renderer = TerminalRenderer(stdscr)
    while True:
        mode = main_menu(stdscr, renderer)
        if mode == "settings":
            settings_menu(stdscr, renderer)
            continue
        if mode == "quit":
            return
        server_handle = None
        server_host = "127.0.0.1"
        try:
            if mode == "host":
                show_progress(stdscr, renderer=renderer)
                max_y, max_x = stdscr.getmaxyx()
                try:
                    server_handle = start_server(max_x, max_y, verbose=False)
                except (OSError, RuntimeError) as exc:
                    frame = renderer.frame()
                    frame.addstr(0, 0, f"Could not start server: {exc}")
                    frame.addstr(2, 0, "Press any key to return to the menu.")
                    renderer.present(frame)
                    stdscr.timeout(-1)
                    stdscr.getch()
                    continue
            elif mode == "join":
                server_host = get_server_ip(stdscr, renderer)
            run_client(stdscr, server_host, PORT, renderer=renderer)
        finally:
            if server_handle is not None:
                server_handle.stop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ttx", description="Play Kard-X Sandbox, a multiplayer terminal RPG."
    )
    parser.add_argument("--version", action="version", version=f"kard-x-sandbox {__version__}")
    parser.parse_args(argv)
    try:
        maximize_terminal()
        curses.wrapper(curses_main)
    except KeyboardInterrupt:
        return 130
    except curses.error as exc:
        print(f"Could not open the game terminal: {exc}", file=sys.stderr)
        return 1
    print("Thanks for playing!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

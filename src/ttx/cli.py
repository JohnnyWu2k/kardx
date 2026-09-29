import curses
import sys
import time

from ttx.net.client import init_colors, run_client
from ttx.net.server import PORT, start_server
from ttx.terminal import TerminalRenderer


def _menu(stdscr, renderer, title: str, options: list[str], subtitle: str = "") -> int:
    stdscr.timeout(-1)
    stdscr.keypad(True)
    selected = 0
    entering = True
    while True:
        frame = renderer.frame()
        frame.addstr(1, 2, title, curses.A_BOLD)
        frame.addstr(2, 2, subtitle)
        for index, option in enumerate(options):
            prefix = "--> " if index == selected else "    "
            frame.addstr(
                4 + index,
                4,
                prefix + option,
                curses.A_REVERSE if index == selected else curses.A_NORMAL,
            )
        if entering:
            renderer.transition(frame)
            entering = False
        else:
            renderer.present(frame)
        key = stdscr.getch()
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
    curses.mousemask(0)
    renderer = renderer or TerminalRenderer(stdscr)
    index = _menu(stdscr, renderer, "TTX", ["Host a game", "Join a game", "Settings", "Quit"],
                  "Side-view sandbox RPG with Kardx card battles")
    return ["host", "join", "settings", "quit"][index]


def get_server_ip(stdscr, renderer=None) -> str:
    renderer = renderer or TerminalRenderer(stdscr)
    frame = renderer.frame()
    frame.addstr(2, 2, "Enter server IP (default 127.0.0.1):")
    renderer.transition(frame)
    stdscr.timeout(-1)
    curses.echo()
    try:
        rows, columns = stdscr.getmaxyx()
        ip = stdscr.getstr(min(3, rows - 1), min(2, columns - 1), max(1, min(64, columns - 3)))
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
    if sys.platform != "win32":
        return
    try:
        import ctypes
    except ImportError:
        return

    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    hwnd = user32.GetForegroundWindow()
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
                server_handle = start_server(max_x, max_y, verbose=False)
            elif mode == "join":
                server_host = get_server_ip(stdscr, renderer)
            run_client(stdscr, server_host, PORT, renderer=renderer)
        finally:
            if server_handle is not None:
                server_handle.stop()


def main():
    maximize_terminal()
    curses.wrapper(curses_main)
    print("Thanks for playing!")


if __name__ == "__main__":
    main()

import argparse
import curses
import sys
import time

from ttx import __version__
from ttx.input import terminal_window
from ttx.net.client import init_colors, run_client
from ttx.net.server import PORT, start_server
from ttx.terminal import TerminalRenderer
from ttx.mouse import enable_mouse, disable_mouse, button, wheel
from ttx.text_input import read_text_key, edit_text, visible_input
from kardx.view_utils import fit_to_width, get_visible_len


def menu_layout(rows: int, columns: int, title: str, options: list[str], subtitle: str = ""):
    """Center a menu and return its clickable button rectangles."""
    button_width = min(columns, max(16, max((get_visible_len(option) for option in options), default=0) + 8))
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
    enable_mouse()
    selected = 0
    entering = True
    while True:
        frame = renderer.frame()
        capacity = max(1, (frame.rows - 6) // 2)
        first = min(max(0, selected - capacity + 1), max(0, len(options) - capacity))
        visible_options = options[first:first + capacity]
        title_y, button_width, buttons = menu_layout(frame.rows, frame.columns, title, visible_options, subtitle)
        frame.addstr(title_y, max(0, (frame.columns - len(title)) // 2), title, curses.A_BOLD)
        frame.addstr(title_y + 2, max(0, (frame.columns - len(subtitle)) // 2), subtitle)
        for index, option in enumerate(visible_options):
            left, top, _, _ = buttons[index]
            inner = max(0, button_width - 4)
            text = fit_to_width(option, inner)
            padding = max(0, inner - get_visible_len(text))
            label = "[ " + " " * (padding // 2) + text + " " * (padding - padding // 2) + " ]"
            frame.addstr(top, left, fit_to_width(label, button_width),
                         curses.A_REVERSE if index + first == selected else curses.A_NORMAL)
        if entering:
            renderer.transition(frame)
            entering = False
        else:
            renderer.present(frame)
        key = stdscr.getch()
        if key == curses.KEY_MOUSE:
            try:
                _, x, y, _, state = curses.getmouse()
            except curses.error:
                continue
            scroll = wheel(state)
            if scroll:
                selected = max(0, min(len(options) - 1, selected + scroll))
            elif button(state):
                clicked = next((i for i, (left, top, right, bottom) in enumerate(buttons)
                                if left <= x < right and top <= y < bottom), None)
                if clicked is not None:
                    return clicked + first
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


def get_server_ip(stdscr, renderer=None) -> str | tuple[str, int] | None:
    renderer = renderer or TerminalRenderer(stdscr)
    stdscr.timeout(-1)
    enable_mouse()
    address = ""
    while True:
        frame = renderer.frame()
        left, top = max(0, (frame.columns - 40) // 2), max(0, frame.rows // 2 - 2)
        frame.addstr(top, left, "Server IP (default 127.0.0.1):")
        frame.addstr(top + 2, left, visible_input(address, min(40, frame.columns - left)))
        frame.addstr(top + 4, left, "[Connect]  [Back]")
        frame.addstr(top + 6, left, "[Search LAN]")
        renderer.present(frame)
        key = read_text_key(stdscr)
        if key == curses.KEY_MOUSE:
            try:
                _, x, y, _, state = curses.getmouse()
            except curses.error:
                continue
            if button(state) and y == top + 6 and left <= x < left + 12:
                from ttx.net.discovery import discover
                show_progress(stdscr, "Searching LAN...", renderer=renderer)
                try:
                    found = discover()
                except OSError:
                    found = []
                selection = _menu(stdscr, renderer, "LAN Worlds", [f"{entry['name']} ({entry['host']})" for entry in found] + ["Back"],
                                  "No worlds found. You can enter the host IP manually." if not found else "Select a world")
                if selection < len(found):
                    return found[selection]["host"], found[selection]["port"]
                continue
            if button(state) and y == top + 4:
                if left <= x < left + 9:
                    key = 10
                elif left + 11 <= x < left + 17:
                    key = 27
        if key in (10, 13, curses.KEY_ENTER):
            return address.strip() or "127.0.0.1"
        if key == 27:
            return None
        address = edit_text(address, key, 253)


def name_world(stdscr, renderer):
    text = ""
    while True:
        frame = renderer.frame()
        left, top = max(0, (frame.columns - 44) // 2), max(0, frame.rows // 2 - 3)
        frame.addstr(top, left, "World name / Unicode supported")
        frame.addstr(top + 2, left, visible_input(text, min(44, frame.columns - left)))
        frame.addstr(top + 4, left, "[Create]  [Back]")
        renderer.present(frame)
        key = read_text_key(stdscr)
        if key == curses.KEY_MOUSE:
            chosen = _mouse_choice([(left, top + 4, left + 8, top + 5), (left + 10, top + 4, left + 16, top + 5)])
            key = 10 if chosen == 0 else 27 if chosen == 1 else key
        if key == 27:
            renderer.invalidate()
            return None
        if key in (10, 13, curses.KEY_ENTER) and text.strip():
            renderer.invalidate()
            return text.strip()
        text = edit_text(text, key)


def host_world(stdscr, renderer):
    from ttx.world.storage import list_worlds, new_world, read_world
    while True:
        worlds = list_worlds()
        selected = _menu(stdscr, renderer, "Host a world", ["Create world"] + ["Load: " + world["name"] for world in worlds] + ["Back"],
                         "Autosave every 30s; Save is also available in Pause")
        if selected == len(worlds) + 1:
            return None
        if selected == 0:
            name = name_world(stdscr, renderer)
            if name:
                return new_world(name)
        else:
            try:
                return read_world(worlds[selected - 1]["id"])
            except (OSError, ValueError) as exc:
                _menu(stdscr, renderer, "Cannot load world", ["Back"], str(exc))


def show_progress(stdscr, message: str = "Starting server...", duration: float = 0.1, renderer=None):
    renderer = renderer or TerminalRenderer(stdscr)
    frame = renderer.frame()
    frame.addstr(max(0, frame.rows // 2 - 1), max(0, (frame.columns - len(message)) // 2), message)
    # Loading is a status frame; the incoming game owns the single reveal.
    renderer.present(frame)
    time.sleep(duration)


def settings_menu(stdscr, renderer=None):
    from kardx.settings import settings_manager
    renderer = renderer or TerminalRenderer(stdscr)
    choices = {
        "battle_particle_color": ["magenta", "cyan", "blue", "green", "gold", "red", "white"],
        "battle_transition_duration": [0.0, 0.2, 0.6, 1.0, 1.5, 2.0, 3.0],
    }
    while True:
        options = ["Fullscreen",
                   f"Particle color: {settings_manager.get('battle_particle_color', 'magenta')}",
                   f"Transition duration: {settings_manager.get('battle_transition_duration', 0.6):g}s",
                   "Preview transition", "Back"]
        selected = _menu(stdscr, renderer, "Settings", options, "Click to cycle; 0s disables the transition")
        if selected == 4:
            return
        if selected == 0:
            maximize_terminal(stdscr)
        elif selected == 3:
            target = renderer.last.copy()
            renderer.begin_battle_transition()
            renderer.complete_battle_transition(target)
        else:
            key = list(choices)[selected - 1]
            values = choices[key]
            current = settings_manager.get(key)
            index = values.index(current) if current in values else -1
            try:
                settings_manager.set(key, values[(index + 1) % len(values)])
            except OSError as exc:
                _menu(stdscr, renderer, "Could not save settings", ["Back"], str(exc))


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
    try:
        return _curses_main(stdscr)
    finally:
        disable_mouse()


def _curses_main(stdscr):
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
                document = host_world(stdscr, renderer)
                if document is None:
                    continue
                show_progress(stdscr, renderer=renderer)
                max_y, max_x = stdscr.getmaxyx()
                try:
                    server_handle = start_server(max_x, max_y, verbose=False, document=document)
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
                if server_host is None:
                    continue
            host, port = server_host if isinstance(server_host, tuple) else (server_host, PORT)
            run_client(stdscr, host, port, renderer=renderer)
        finally:
            if server_handle is not None:
                server_handle.stop()
                if server_handle.runtime.error:
                    _menu(stdscr, renderer, "World error", ["Back"], str(server_handle.runtime.error))


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

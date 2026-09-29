from __future__ import annotations

import curses
import json
import math
import socket
import threading
import time

from ttx.combat.card_battle import run_card_battle
from ttx.input import MotionInput, windows_key_state
from ttx.terminal import CardTerminal, Frame, TerminalRenderer
from ttx.world.map import InfiniteGameMap

PORT = 12345
game_state: dict = {}
UI_WIDTH_RATIO = 0.25
MIN_PANEL_WIDTH = 18
FRAME_INTERVAL = 1 / 30
CONTROL_HEARTBEAT = 0.10


def layout_columns(max_x: int) -> tuple[int, int, int]:
    """Return game width, UI panel x, and UI panel width within terminal bounds."""
    if max_x <= 2:
        return max(0, max_x), max_x, 0
    ui_width = min(max(MIN_PANEL_WIDTH, round(max_x * UI_WIDTH_RATIO)), max_x - 2)
    game_width = max(1, max_x - ui_width - 1)
    panel_x = min(max_x, game_width + 1)
    panel_width = max(0, max_x - panel_x)
    return game_width, panel_x, panel_width


def reset_client_state():
    game_state.clear()


def network_listener(sock: socket.socket, stop_event: threading.Event):
    global game_state
    buffer = b""
    try:
        sock.settimeout(0.05)
        while not stop_event.is_set():
            try:
                data = sock.recv(4096)
            except socket.timeout:
                continue
            if not data:
                break
            buffer += data
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                if line.strip():
                    game_state = json.loads(line)
    except (OSError, ValueError):
        pass
    finally:
        stop_event.set()


class Game:
    def __init__(self, stdscr, sock: socket.socket, renderer=None, stop_event=None):
        self.stdscr = stdscr
        self.sock = sock
        self.game_map: InfiniteGameMap | None = None
        self.quit_to_menu = False
        self.scale = 1
        self.active_inventory_slot = 0
        self.inventory = ["wood", "stone", "dirt", "sand", None]
        self.building_mode_active = False
        self.build_direction = (1, 0)
        self.mouse_raw_x: int | None = None
        self.mouse_raw_y: int | None = None
        self.card_player_id = "player_balanced"
        self.card_deck_ids: list[str] | None = None
        self.card_hp: int | None = None
        self.card_max_hp: int | None = None
        self.card_base_mana: int | None = None
        self._dirty = True
        self._last_render = 0.0
        self._renderer = renderer or TerminalRenderer(stdscr)
        self._controls = MotionInput(windows_key_state())
        self._last_direction = 0
        self._last_control_send = 0.0
        self._render_state = None
        self._canvas = None
        self._camera = None
        self._camera_time = 0.0
        self._stop_event = stop_event
        self._notice = ""
        self._notice_until = 0.0

        curses.curs_set(0)
        self.stdscr.nodelay(True)
        self.stdscr.timeout(0)
        curses.mousemask(0)
        self.stdscr.keypad(True)
        if hasattr(curses, "set_escdelay"):
            curses.set_escdelay(25)

    @property
    def state(self):
        state = getattr(self, "_render_state", None)
        return game_state if state is None else state

    @property
    def canvas(self):
        return getattr(self, "_canvas", None) or self.stdscr

    def _terminal_renderer(self):
        renderer = getattr(self, "_renderer", None)
        if renderer is None or renderer.screen is not self.stdscr:
            self._renderer = TerminalRenderer(self.stdscr)
        return self._renderer

    def _motion_input(self):
        if not hasattr(self, "_controls"):
            self._controls = MotionInput()
        return self._controls

    def wait_for_map_seed(self):
        deadline = time.monotonic() + 5.0
        while "map_seed" not in game_state:
            if time.monotonic() >= deadline or (getattr(self, "_stop_event", None) and self._stop_event.is_set()):
                return False
            time.sleep(0.02)
        self.game_map = InfiniteGameMap(
            game_state["world_width"], seed=game_state["map_seed"],
            height=game_state["world_height"],
        )
        return True

    def process_input(self) -> bool:
        key = self.stdscr.getch()
        if key == -1:
            return True
        return self.process_key(key)

    def process_key(self, key: int) -> bool:
        if key == curses.KEY_MOUSE:
            self._handle_mouse()
            return True
        if key == 27:
            return self._pause()
        try:
            ch = chr(key).lower()
        except ValueError:
            ch = ""
        if ch in ["1", "2", "3", "4", "5"]:
            self.active_inventory_slot = int(ch) - 1
            self._dirty = True
            return True
        if ch == "b":
            self._stop_controls()
            self.building_mode_active = not self.building_mode_active
            self._dirty = True
            return True
        if ch == "g":
            dx, dy = self.build_direction if self.building_mode_active else (int((self._my_player() or {}).get("facing", 1)), 0)
            self._send({"gather": True, "dx": dx, "dy": dy})
            return True
        if ch == "x":
            self._fight_adjacent_enemy()
            return True

        arrow = {curses.KEY_LEFT: "a", curses.KEY_RIGHT: "d", curses.KEY_UP: "w", curses.KEY_DOWN: "s"}
        ch = arrow.get(key, ch)
        if self.building_mode_active:
            directions = {"w": (0, -1), "s": (0, 1), "a": (-1, 0), "d": (1, 0)}
            if ch in directions:
                self.build_direction = directions[ch]
                self._dirty = True
            elif key in (10, 13, curses.KEY_ENTER):
                self._place_block()
            return True
        if ch in ("w", " "):
            self._motion_input().feed(ch)
        elif ch == "s":
            self._send({"gather": True, "dx": 0, "dy": 1})
        elif ch in ("a", "d"):
            self._motion_input().feed(ch)
        return True

    def _update_controls(self, now: float):
        if self.building_mode_active:
            return
        direction, jumped = self._motion_input().sample(now)
        if (jumped or direction != getattr(self, "_last_direction", 0) or
                direction and now - getattr(self, "_last_control_send", 0) >= CONTROL_HEARTBEAT):
            message = {"move": direction}
            if jumped:
                message["jump"] = True
            self._send(message)
            self._last_direction, self._last_control_send = direction, now

    def _stop_controls(self):
        self._motion_input().reset()
        self._send({"move": 0})
        self._last_direction = 0
        self._last_control_send = time.monotonic()

    def _compose_frame(self) -> Frame:
        frame = self._terminal_renderer().frame()
        self._canvas = frame
        self._render_state = game_state
        try:
            self._draw_world()
        finally:
            self._canvas = None
            self._render_state = None
        return frame

    def render(self, transition: bool = False):
        frame = self._compose_frame()
        renderer = self._terminal_renderer()
        if transition:
            renderer.transition(frame)
        else:
            renderer.present(frame)

    def _draw_world(self):
        max_y, max_x = self.stdscr.getmaxyx()
        game_width, panel_x, panel_width = layout_columns(max_x)
        camera_x, camera_y = self._camera_offset()
        if self.game_map:
            tiles = self.state.get("custom_tiles", {})
            revision = self.state.get("terrain_revision")
            if revision is None:
                revision = tuple(sorted((key, tile["char"]) for key, tile in tiles.items()))
            key = (id(self.game_map), camera_x, camera_y, max_y, max_x, self.scale, revision)
            if getattr(self, "_terrain_key", None) == key:
                self.canvas.cells = [row.copy() for row in self._terrain_frame.cells]
            else:
                self.game_map.draw_scaled(
                    self.canvas, scale=self.scale, camera_x=camera_x, camera_y=camera_y,
                    width_limit=game_width, custom_tiles=tiles,
                )
                self._terrain_key, self._terrain_frame = key, self.canvas.copy()
        self._draw_entities(camera_x, camera_y, game_width, max_y)
        if self.building_mode_active:
            player = self._my_player()
            if player:
                dx, dy = self.build_direction
                self._draw_at({"x": int(player["x"]) + dx, "y": int(player["y"]) + dy, "char": "+"},
                              camera_x, camera_y, game_width, max_y, curses.A_REVERSE)
        self._draw_divider(game_width, max_y)
        self._draw_ui_panel(panel_x, panel_width, max_y)

    def run(self) -> str:
        if not self.wait_for_map_seed():
            return "quit_to_menu"
        self.render(transition=True)
        running = True
        while running:
            # Bound the drain so a key-repeat flood cannot starve rendering.
            for _ in range(64):
                key = self.stdscr.getch()
                if key == -1:
                    break
                running = self.process_key(key)
                if not running:
                    break
            now = time.monotonic()
            if not running or self.quit_to_menu or (self._stop_event and self._stop_event.is_set()):
                break
            self._update_controls(now)
            if self._dirty or now - self._last_render >= FRAME_INTERVAL:
                self.render()
                self._dirty = False
                self._last_render = now
            time.sleep(0.005)
        self._stop_controls()
        return "quit_to_menu" if self.quit_to_menu else "exit"

    def _handle_mouse(self):
        try:
            _, mx, my, _, bstate = curses.getmouse()
        except curses.error:
            return
        self.mouse_raw_x = mx
        self.mouse_raw_y = my

    def _pause(self) -> bool:
        self._stop_controls()
        options = ["Resume", "Quit"]
        selected = 0
        renderer = self._terminal_renderer()
        self.stdscr.timeout(50)
        try:
            while True:
                frame = self._compose_frame()
                width = min(28, frame.columns)
                left, top = max(0, (frame.columns - width) // 2), max(0, (frame.rows - 7) // 2)
                panel = ["+" + "-" * max(0, width - 2) + "+",
                         "|" + "Paused".center(max(0, width - 2)) + "|",
                         "|" + " " * max(0, width - 2) + "|"]
                panel.extend("|" + (("> " if index == selected else "  ") + option).ljust(max(0, width - 2)) + "|"
                             for index, option in enumerate(options))
                panel.extend(["|" + " " * max(0, width - 2) + "|", panel[0]])
                for row, line in enumerate(panel):
                    frame.addstr(top + row, left, line, curses.A_REVERSE if row == 3 + selected else 0)
                renderer.present(frame)
                key = self.stdscr.getch()
                if key == curses.KEY_UP:
                    selected = max(0, selected - 1)
                elif key == curses.KEY_DOWN:
                    selected = min(len(options) - 1, selected + 1)
                elif key == 27:
                    return True
                elif key in (curses.KEY_ENTER, 10, 13):
                    if selected == 1:
                        self.quit_to_menu = True
                        return False
                    return True
                if self._stop_event and self._stop_event.is_set():
                    self.quit_to_menu = True
                    return False
        finally:
            self.stdscr.timeout(0)
            self._motion_input().reset()
            curses.flushinp()
            self._dirty = True

    def _fight_adjacent_enemy(self):
        target_enemy_id, enemy = self._adjacent_enemy()
        if not target_enemy_id or not enemy:
            return
        self._stop_controls()
        self._send({"battle": "start", "enemy_id": target_enemy_id})
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if (self._my_player() or {}).get("battle_enemy") == target_enemy_id:
                break
            time.sleep(0.02)
        else:
            self._send({"battle": "end"})
            return
        enemy_card_id = enemy.get("card_enemy_id", "enemy_giant_rat")
        curses.flushinp()
        try:
            result = run_card_battle(
                enemy_id=enemy_card_id,
                player_id=self.card_player_id,
                deck_ids=self.card_deck_ids,
                hp=self.card_hp,
                max_hp=self.card_max_hp,
                base_mana=self.card_base_mana,
                terminal=CardTerminal(self._terminal_renderer()),
            )
            self.card_hp = result.hp
            self.card_max_hp = result.max_hp
            self.card_base_mana = result.base_mana
            self.card_deck_ids = result.deck_ids
            if result.victory:
                self._send({"attack": True, "enemy_id": target_enemy_id, "defeated": True})
            self._notice = "Victory!" if result.victory else "Battle ended"
            self._notice_until = time.monotonic() + 2.0
        finally:
            self._send({"battle": "end"})
            self.stdscr.timeout(0)
            self._motion_input().reset()
            curses.flushinp()
            self.render(transition=True)

    def _send(self, message: dict):
        try:
            self.sock.sendall((json.dumps(message) + "\n").encode())
        except OSError:
            self.quit_to_menu = True

    def _my_player(self) -> dict | None:
        players = self.state.get("players", {})
        client_id = self.state.get("client_id")
        if client_id and client_id in players:
            return players[client_id]
        return next(iter(players.values()), None) if players else None

    def _camera_offset(self) -> tuple[int, int]:
        max_y, max_x = self.stdscr.getmaxyx()
        player = self._my_player()
        if not player:
            return 0, 0
        visible_rows = max(1, max_y // self.scale)
        game_width, _, _ = layout_columns(max_x)
        visible_cols = max(1, game_width // self.scale)
        width = self.game_map.width if self.game_map else visible_cols
        height = self.game_map.height if self.game_map else visible_rows
        px = float(player.get("x", 0)) + float(player.get("horizontal_progress", 0))
        py = float(player.get("y", 0)) + float(player.get("vertical_progress", 0))
        limits = max(0, width - visible_cols), max(0, height - visible_rows)
        center = [max(0, min(limits[0], px - visible_cols // 2)),
                  max(0, min(limits[1], py - visible_rows // 2))]
        previous = getattr(self, "_camera", None)
        now = time.monotonic()
        if previous is None or abs(previous[0] - center[0]) > visible_cols or abs(previous[1] - center[1]) > visible_rows:
            camera = center
        else:
            camera = list(previous)
            elapsed = min(0.1, max(0, now - self._camera_time))
            alpha = 1 - math.exp(-12 * elapsed)
            for axis, (position, visible) in enumerate(((px, visible_cols), (py, visible_rows))):
                offset = position - (camera[axis] + visible // 2)
                dead_zone = max(1, visible // 6)
                if abs(offset) > dead_zone:
                    target = camera[axis] + offset - math.copysign(dead_zone, offset)
                    camera[axis] += (target - camera[axis]) * alpha
                camera[axis] = max(0, min(limits[axis], camera[axis]))
        self._camera, self._camera_time = camera, now
        return round(camera[0]), round(camera[1])

    def _place_block(self):
        player = self._my_player()
        material = self.inventory[self.active_inventory_slot]
        if player is None or material is None:
            return
        dx, dy = self.build_direction
        self._send({"build": True, "x": int(player["x"]) + dx,
                    "y": int(player["y"]) + dy, "material": material})

    def _adjacent_enemy(self) -> tuple[str | None, dict | None]:
        player = self._my_player()
        if not player:
            return None, None
        px, py = int(player.get("x", 0)), int(player.get("y", 0))
        for enemy_id, enemy in self.state.get("enemies", {}).items():
            ex, ey = int(enemy.get("x", 0)), int(enemy.get("y", 0))
            if abs(ex - px) + abs(ey - py) == 1:
                return enemy_id, enemy
        return None, None

    def _draw_entities(self, camera_x: int, camera_y: int, game_width: int, max_y: int):
        for obj in self.state.get("objects", {}).values():
            attr = curses.color_pair(2) if obj.get("type") == "tree" else curses.color_pair(4)
            self._draw_at(obj, camera_x, camera_y, game_width, max_y, attr)
            if obj.get("type") == "tree":
                self._draw_at({**obj, "y": int(obj["y"]) - 1, "char": "^"},
                              camera_x, camera_y, game_width, max_y, curses.color_pair(2))
        for enemy in self.state.get("enemies", {}).values():
            attr = curses.color_pair(5) | (curses.A_BOLD if enemy.get("mode") == "chase" else 0)
            self._draw_at(enemy, camera_x, camera_y, game_width, max_y, attr)
        for player in self.state.get("players", {}).values():
            self._draw_at(player, camera_x, camera_y, game_width, max_y, curses.A_BOLD)

    def _draw_at(self, entity: dict, camera_x: int, camera_y: int, game_width: int, max_y: int, attr: int):
        x, y = int(entity.get("x", 0)), int(entity.get("y", 0))
        char = str(entity.get("char", "?"))[0]
        screen_x = (x - camera_x) * self.scale
        screen_y = (y - camera_y) * self.scale
        if 0 <= screen_x < game_width and 0 <= screen_y < max_y:
            try:
                self.canvas.addch(screen_y, screen_x, char, attr)
            except curses.error:
                pass

    def _draw_divider(self, game_width: int, max_y: int):
        for row in range(max_y):
            try:
                self.canvas.addch(row, game_width, "|")
            except curses.error:
                pass

    def _draw_ui_panel(self, panel_x: int, panel_width: int, max_y: int):
        if panel_width <= 0 or max_y <= 0:
            return
        self._draw_box(panel_x, panel_width, max_y)
        player = self._my_player() or {}
        content_x = panel_x + 2
        self._safe_addstr(1, content_x, "TTX", panel_width - 3)
        hp = self.card_hp if self.card_hp is not None else player.get("hp", 50)
        self._safe_addstr(3, content_x, f"HP: {hp}", panel_width - 3)
        self._safe_addstr(4, content_x, f"Gold: {player.get('gold', 0)}", panel_width - 3)
        self._safe_addstr(5, content_x, f"Pos: {player.get('x', 0)},{player.get('y', 0)}", panel_width - 3)
        self._safe_addstr(7, content_x, "A/D walk", panel_width - 3)
        self._safe_addstr(8, content_x, "W/Space jump", panel_width - 3)
        self._safe_addstr(9, content_x, "G gather / mine", panel_width - 3)
        self._safe_addstr(10, content_x, "S mine below", panel_width - 3)
        self._safe_addstr(11, content_x, "X card battle", panel_width - 3)
        self._safe_addstr(12, content_x, "B toggle build", panel_width - 3)
        selected = self.inventory[self.active_inventory_slot] or "empty"
        self._safe_addstr(14, content_x, f"Build: {'ON' if self.building_mode_active else 'OFF'}", panel_width - 3)
        self._safe_addstr(15, content_x, "1 wood / 2 stone", panel_width - 3)
        self._safe_addstr(16, content_x, f"Selected: {selected}", panel_width - 3)
        self._safe_addstr(17, content_x, "3 dirt / 4 sand", panel_width - 3)
        self._safe_addstr(18, content_x, "WASD aim; Enter place", panel_width - 3)
        if getattr(self, "_notice", "") and time.monotonic() < self._notice_until:
            self._safe_addstr(max_y - 2, content_x, self._notice, panel_width - 3)
        inventory = player.get("inventory", {})
        self._safe_addstr(19, content_x, "Materials:", panel_width - 3)
        row = 20
        for item_id, amount in sorted(inventory.items()):
            if row >= max_y - 2:
                break
            self._safe_addstr(row, content_x, f"{item_id}: {amount}", panel_width - 3)
            row += 1

    def _draw_box(self, x: int, width: int, height: int):
        if width < 2 or height < 2:
            return
        right = x + width - 1
        bottom = height - 1
        for col in range(x, x + width):
            try:
                self.canvas.addch(0, col, "-")
                self.canvas.addch(bottom, col, "-")
            except curses.error:
                pass
        for row in range(height):
            try:
                self.canvas.addch(row, x, "|")
                self.canvas.addch(row, right, "|")
            except curses.error:
                pass
        for row, col in ((0, x), (0, right), (bottom, x), (bottom, right)):
            try:
                self.canvas.addch(row, col, "+")
            except curses.error:
                pass

    def _safe_addstr(self, y: int, x: int, text: str, width: int):
        if width <= 0:
            return
        try:
            self.canvas.addstr(y, x, text[:width])
        except curses.error:
            pass


def run_client(stdscr, server_host: str, server_port: int = PORT, renderer=None):
    reset_client_state()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass
    try:
        sock.connect((server_host, server_port))
    except OSError as exc:
        terminal = renderer or TerminalRenderer(stdscr)
        frame = terminal.frame()
        frame.addstr(0, 0, f"Could not connect to server: {exc}")
        terminal.present(frame)
        sock.close()
        time.sleep(1)
        return "quit_to_menu"
    stop_event = threading.Event()
    listener = threading.Thread(target=network_listener, args=(sock, stop_event), daemon=False)
    listener.start()
    try:
        game = Game(stdscr, sock, renderer=renderer, stop_event=stop_event)
        return game.run()
    finally:
        stop_event.set()
        try:
            sock.sendall((json.dumps({"disconnect": True}) + "\n").encode())
        except OSError:
            pass
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()
        listener.join(timeout=1.0)


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_WHITE, -1)
    curses.init_pair(4, curses.COLOR_CYAN, -1)
    curses.init_pair(5, curses.COLOR_RED, -1)
    curses.init_pair(6, curses.COLOR_YELLOW, -1)
    curses.init_pair(7, curses.COLOR_YELLOW, -1)
    curses.init_pair(8, curses.COLOR_BLUE, -1)
    curses.init_pair(9, curses.COLOR_MAGENTA, -1)

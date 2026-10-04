from __future__ import annotations

import curses
import json
import math
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from ttx.combat.card_battle import prepare_card_battle, run_card_battle
from ttx.input import MotionInput, windows_key_state
from ttx.mouse import enable_mouse, button, wheel
from ttx.terminal import CardTerminal, Frame, TerminalRenderer
from ttx.net.prediction import LocalPrediction, RemoteInterpolation
from ttx.net.protocol import SNAPSHOT_LIMIT, JsonLineReader, ProtocolError, valid_snapshot
from ttx.world.camera import Camera
from ttx.world.animation import ActorAnimation
from ttx.world.materials import init_material_colors
from ttx.world.map import InfiniteGameMap
from ttx.world.crafting import RECIPES, TILES, TOOLS
from ttx.world.inventory import BACKPACK_SIZE, HOTBAR_SIZE, BLOCKS, SYMBOLS, hotbar_key, sync_slots
from ttx.world.physics import position
from ttx.world.render import TILE_PIXELS, DotCanvas, actor_sprite, marker, origin, project, terrain, tree_sprite

PORT = 12345
game_state: dict = {}
UI_WIDTH_RATIO = 0.25
MIN_PANEL_WIDTH = 18
FRAME_INTERVAL = 1 / 60
MOUSE_REPEAT_INTERVAL = 0.12


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
    global game_state
    game_state = {}


def network_listener(sock: socket.socket, stop_event: threading.Event):
    global game_state
    reader = JsonLineReader(SNAPSHOT_LIMIT)
    try:
        sock.settimeout(0.2)
        while not stop_event.is_set():
            try:
                data = sock.recv(4096)
            except socket.timeout:
                continue
            if not data:
                break
            for state in reader.feed(data):
                if not valid_snapshot(state):
                    raise ProtocolError("Invalid world snapshot.")
                state["received_at"] = time.monotonic()
                game_state = state
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
        self.smooth_graphics = True
        self.active_inventory_slot = 0
        self.inventory = [None] * BACKPACK_SIZE
        self._inventory_loaded = False
        self.aim_visible = True
        self.build_direction = (1, 0)
        self.mouse_raw_x: int | None = None
        self.mouse_raw_y: int | None = None
        self.card_player_id = "player_balanced"
        self.card_deck_ids: list[str] | None = None
        self.card_hp: int | None = None
        self.card_max_hp: int | None = None
        self.card_base_mana: int | None = None
        self._card_rewards_received = 0
        self._dirty = True
        self._last_render = 0.0
        self._renderer = renderer or TerminalRenderer(stdscr)
        self._controls = MotionInput(windows_key_state())
        self._mouse_down = False
        self._mouse_action = None
        self._next_mouse_action = 0.0
        self._last_direction = 0
        self._render_state = None
        self._canvas = None
        self._camera = Camera()
        self._prediction = None
        self._remote_interpolation = RemoteInterpolation()
        self._paused = False
        self._dot_canvas = None
        self._stop_event = stop_event
        self._notice = ""
        self._notice_until = 0.0

        curses.curs_set(0)
        self.stdscr.nodelay(True)
        self.stdscr.timeout(0)
        enable_mouse()
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
        if key == curses.KEY_RESIZE:
            self._stop_mouse_action()
            self.mouse_raw_x = self.mouse_raw_y = None
            self.render()
            self._dirty = True
            return True
        if key == curses.KEY_MOUSE:
            self._handle_mouse()
            return True
        if key == 27:
            return self._pause()
        try:
            ch = chr(key).lower()
        except ValueError:
            ch = ""
        slot = hotbar_key(key)
        if slot is not None:
            self._stop_mouse_action()
            self.active_inventory_slot = slot
            self.aim_visible = True
            self._dirty = True
            return True
        if ch == "e":
            self._inventory_menu()
            return True
        if ch == "v":
            self._stop_mouse_action()
            self.smooth_graphics = not self.smooth_graphics
            self._camera = Camera()
            self._dirty = True
            return True
        if ch == "c":
            self._craft_menu()
            return True
        arrow = {curses.KEY_LEFT: "a", curses.KEY_RIGHT: "d", curses.KEY_UP: "w", curses.KEY_DOWN: "s"}
        ch = arrow.get(key, ch)
        if key in (10, 13, curses.KEY_ENTER):
            self._place_block()
            return True
        if ch in ("w", " ", "a", "d"):
            controls = self._motion_input()
            if controls.key_state is None:
                controls.feed(ch)
        return True

    def _update_controls(self, now: float):
        if getattr(self, "_paused", False):
            return
        direction, jumped = self._motion_input().sample(now)
        packet = game_state
        prediction = self._local_prediction(now, packet)
        if prediction:
            prediction.advance(now, direction, jumped, lambda x, y: self._prediction_blocked(x, y, packet), self._send)
        if direction != getattr(self, "_last_direction", 0) or jumped:
            self._dirty = True
        self._last_direction = direction

    def _server_player(self, state=None) -> dict | None:
        state = game_state if state is None else state
        players = state.get("players", {})
        client_id = state.get("client_id")
        return players.get(client_id) if client_id else next(iter(players.values()), None)

    def _controlled_player(self) -> dict | None:
        prediction = getattr(self, "_prediction", None)
        return prediction.actor if prediction else self._my_player()

    def _prediction_blocked(self, x: int, y: int, state=None) -> bool:
        if self.game_map is None:
            return True
        state = game_state if state is None else state
        override = state.get("custom_tiles", {}).get(f"{x},{y}")
        tile = override["char"] if override else self.game_map.get_tile(x, y)
        if tile != self.game_map.AIR:
            return True
        client_id = state.get("client_id")
        for group in ("players", "enemies"):
            for actor_id, actor in state.get(group, {}).items():
                if group == "players" and (actor_id == client_id or actor is self._server_player(state)):
                    continue
                if int(actor["x"]) == x and int(actor["y"]) == y:
                    return True
        return False

    def _local_prediction(self, now: float, packet=None):
        packet = game_state if packet is None else packet
        authoritative = self._server_player(packet)
        if not authoritative:
            return None
        if getattr(self, "_prediction", None) is None:
            self._prediction = LocalPrediction(authoritative, now)
        self._prediction.reconcile(authoritative, packet, lambda x, y: self._prediction_blocked(x, y, packet))
        return self._prediction

    def _view_state(self, now: float) -> dict:
        packet = game_state
        self._sync_card_rewards(packet)
        player = self._server_player(packet) or {}
        self._sync_inventory(player)
        notice = player.get("notice", "")
        if notice and notice != getattr(self, "_server_notice", ""):
            self._server_notice = notice
            self._notify(notice)
        state = dict(packet)
        interpolation = getattr(self, "_remote_interpolation", None)
        if interpolation is None:
            interpolation = self._remote_interpolation = RemoteInterpolation()
        interpolation.update(packet, now)
        positions = interpolation.positions(now)
        for group in ("players", "enemies"):
            state[group] = {}
            for actor_id, actor in packet.get(group, {}).items():
                display = dict(actor)
                if (not packet.get("world_paused") and not actor.get("paused")
                        and not actor.get("engaged_by") and not actor.get("battle_enemy")):
                    display["display_position"] = positions.get((group, actor_id), position(actor))
                state[group][actor_id] = display
        prediction = self._local_prediction(now, packet)
        if prediction:
            client_id = packet.get("client_id") or next(iter(state["players"]), None)
            state["players"][client_id] = dict(prediction.actor)
        animations = getattr(self, "_animations", {})
        active = {}
        for group in ("players", "enemies"):
            for actor_id, actor in state[group].items():
                key = group, actor_id
                animation = active[key] = animations.get(key) or ActorAnimation()
                frozen = bool(packet.get("world_paused") or actor.get("paused")
                              or actor.get("engaged_by") or actor.get("battle_enemy"))
                state[group][actor_id] = animation.sample(actor, now, frozen)
        self._animations = active
        return state

    def _sync_inventory(self, player=None):
        player = (self._server_player() or {}) if player is None else player
        slots = getattr(self, "inventory", [])
        if not getattr(self, "_inventory_loaded", False) and player.get("profile_ready", True):
            slots = player.get("inventory_order", slots)
            self._inventory_loaded = True
        self.inventory = sync_slots(slots, player.get("inventory", {}))
        return self.inventory

    def _selected_item(self):
        slots = self._sync_inventory()
        return slots[self.active_inventory_slot % HOTBAR_SIZE]

    def _stop_controls(self):
        self._stop_mouse_action()
        self._mouse_down = False
        self._motion_input().reset()
        prediction = getattr(self, "_prediction", None)
        if prediction:
            command = prediction.release(time.monotonic())
            if command:
                self._send(command)
        else:
            self._send({"stop": True})
        self._last_direction = 0

    def _compose_frame(self) -> Frame:
        frame = self._terminal_renderer().frame()
        self._canvas = frame
        self._dot_canvas = None
        self._frame_time = time.monotonic()
        self._render_state = self._view_state(self._frame_time)
        try:
            self._draw_world()
        finally:
            self._canvas = None
            self._render_state = None
            self._dot_canvas = None
        return frame

    def render(self, transition: bool = False):
        frame = self._compose_frame()
        renderer = self._terminal_renderer()
        if transition:
            renderer.transition(frame)
        else:
            renderer.present(frame)

    def _draw_world(self):
        max_y, max_x = self.canvas.getmaxyx()
        game_width, panel_x, panel_width = layout_columns(max_x)
        camera_x, camera_y = self._camera_offset()
        self._display_camera = (camera_x, camera_y)
        self._aim_actors = [dict(actor) for group in ("enemies", "objects")
                            for actor in self.state.get(group, {}).values()]
        smooth = getattr(self, "smooth_graphics", True)
        if self.game_map:
            tiles = self.state.get("custom_tiles", {})
            revision = self.state.get("terrain_revision")
            if revision is None:
                revision = tuple(sorted((key, tile["char"]) for key, tile in tiles.items()))
            camera_key = origin((camera_x, camera_y)) if smooth else (camera_x, camera_y)
            key = (id(self.game_map), camera_key, max_y, max_x, self.scale, revision, smooth)
            if getattr(self, "_terrain_key", None) == key:
                if smooth:
                    self._dot_canvas = self._terrain_frame.copy()
                else:
                    self.canvas.cells = [row.copy() for row in self._terrain_frame.cells]
            else:
                if smooth:
                    self._dot_canvas = DotCanvas(max_y, game_width)
                    attributes = {tile: self.game_map._tile_attr(tile) for tile in self.game_map.SOLID_TILES}
                    terrain(self._dot_canvas, self.game_map, (camera_x, camera_y), tiles, attributes)
                    self._terrain_frame = self._dot_canvas.copy()
                else:
                    self.game_map.draw_scaled(
                        self.canvas, scale=self.scale, camera_x=camera_x, camera_y=camera_y,
                        width_limit=game_width, custom_tiles=tiles,
                    )
                    self._terrain_frame = self.canvas.copy()
                self._terrain_key = key
        self._draw_entities(camera_x, camera_y, game_width, max_y)
        if getattr(self, "aim_visible", True) and self._mouse_target() is not None:
            player = self._my_player()
            if player:
                dx, dy = self.build_direction
                target = self._mouse_target() or (int(player["x"]) + dx, int(player["y"]) + dy)
                aim = {"x": target[0], "y": target[1], "char": "+"}
                reach = 2 if self._selected_item() in BLOCKS else 1
                aim_attr = curses.color_pair(4 if self._in_reach(target, reach) else 5) | curses.A_BOLD
                if smooth and self._dot_canvas:
                    marker(self._dot_canvas, aim, (camera_x, camera_y), aim_attr)
                else:
                    self._draw_at(aim, camera_x, camera_y, game_width, max_y, aim_attr | curses.A_REVERSE)
        if self._dot_canvas:
            self._dot_canvas.paint(self.canvas)
        self._draw_divider(game_width, max_y)
        self._draw_ui_panel(panel_x, panel_width, max_y)

    def run(self) -> str:
        if not self.wait_for_map_seed():
            return "quit_to_menu"
        deadline = time.monotonic() + 1
        while not (self._server_player() or {}).get("profile_ready") and time.monotonic() < deadline:
            time.sleep(0.01)
        progress = (self._server_player() or {}).get("card_progress")
        if progress:
            self.card_hp, self.card_max_hp = progress["hp"], progress["max_hp"]
            self.card_base_mana, self.card_deck_ids = progress["mana"], list(progress["deck"])
            self._card_rewards_received = progress.get("rewards_received", 0)
        self.render(transition=True)
        next_frame = time.monotonic()
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
            self._update_mouse_action(now)
            if self._dirty or now >= next_frame:
                self.render()
                self._dirty = False
                self._last_render = now
                if now >= next_frame:
                    next_frame += FRAME_INTERVAL
                    if next_frame < now:
                        next_frame = now + FRAME_INTERVAL
            time.sleep(max(0.0005, min(0.002, next_frame - time.monotonic())))
        self._stop_controls()
        self._persist_card_progress()
        return "quit_to_menu" if self.quit_to_menu else "exit"

    def _mouse_target(self):
        mx, my = getattr(self, "mouse_raw_x", None), getattr(self, "mouse_raw_y", None)
        if mx is None or my is None:
            return None
        rows, columns = self.canvas.getmaxyx()
        game_width, _, _ = layout_columns(columns)
        if mx is None or my is None or not (0 <= mx < game_width and 0 <= my < rows):
            return None
        camera = getattr(self, "_display_camera", (0, 0))
        if getattr(self, "smooth_graphics", True):
            # A sprite's center can sit on a character-cell boundary. Prefer
            # the visible actor over the terrain at the cell's other half.
            actors = getattr(self, "_aim_actors", None)
            if actors is None:
                actors = [actor for group in ("enemies", "objects")
                          for actor in self.state.get(group, {}).values()]
            for actor in actors:
                sx, sy = project(actor, camera)
                if (sx // 2, sy // 4) == (mx, my):
                    return int(actor["x"]), int(actor["y"])
            ox, oy = origin(camera)
            return (mx * 2 + 1 + ox) // TILE_PIXELS, (my * 4 + 2 + oy) // TILE_PIXELS
        return math.floor(mx / self.scale + camera[0]), math.floor(my / self.scale + camera[1])

    def _in_reach(self, target, reach):
        player = self._controlled_player()
        return bool(player and 0 < abs(target[0] - int(player["x"])) + abs(target[1] - int(player["y"])) <= reach)

    def _notify(self, message):
        self._notice, self._notice_until = message, time.monotonic() + 2.5
        self._dirty = True

    def _stop_mouse_action(self):
        self._mouse_action = None

    def _update_mouse_action(self, now):
        if not getattr(self, "_mouse_down", False):
            return
        native = self._motion_input().key_state
        if native and not getattr(native, "mouse_down", lambda: True)():
            self._mouse_down = False
            self._stop_mouse_action()
        action = getattr(self, "_mouse_action", None)
        if action is None:
            return
        if getattr(self, "_paused", False) or action != (self.active_inventory_slot, self._selected_item()):
            # A depleted block stack must never turn into bare-hand digging.
            self._stop_mouse_action()
            return
        target = self._mouse_target()
        if target is None:
            self._stop_mouse_action()
            return
        if now >= self._next_mouse_action:
            # No catch-up burst after a slow frame or a delayed network reply.
            self._next_mouse_action = now + MOUSE_REPEAT_INTERVAL
            self._use_mouse_target(target, action[1], repeat=True)

    def _use_mouse_target(self, target, item, *, repeat=False):
        if item in BLOCKS:
            if not repeat or self._in_reach(target, 2) and not self._prediction_blocked(*target):
                self._place_block(target)
            return
        if not self._in_reach(target, 1):
            if not repeat:
                self._notify("Attack / mine reach: 1 tile")
            return
        enemy_id = next((key for key, actor in self.state.get("enemies", {}).items()
                         if (int(actor["x"]), int(actor["y"])) == target), None)
        if enemy_id:
            self._stop_mouse_action()
            if not repeat:
                self._fight_adjacent_enemy(enemy_id)
            return
        if repeat and self._target_tile(target) == InfiniteGameMap.AIR and not any(
            (int(obj["x"]), int(obj["y"])) == target for obj in self.state.get("objects", {}).values()
        ):
            return
        player = self._controlled_player()
        self._send({"gather": True, "dx": target[0] - int(player["x"]),
                    "dy": target[1] - int(player["y"]), "tool": item if item in TOOLS else None})

    def _handle_mouse(self):
        try:
            _, mx, my, _, state = curses.getmouse()
        except curses.error:
            return
        self.mouse_raw_x, self.mouse_raw_y = mx, my
        self._dirty = True
        if state & curses.BUTTON1_RELEASED:
            self._mouse_down = False
            self._stop_mouse_action()
        clicked = bool(state & curses.BUTTON1_CLICKED)
        pressed = bool(state & curses.BUTTON1_PRESSED)
        fresh_press = clicked or pressed and not getattr(self, "_mouse_down", False)
        if clicked:
            self._mouse_down = False
            self._stop_mouse_action()
        elif pressed:
            self._mouse_down = True
        if button(state, 3):
            self._stop_mouse_action()
            self.aim_visible = False
            return
        scroll = wheel(state)
        if scroll:
            self._stop_mouse_action()
            self.active_inventory_slot = (self.active_inventory_slot + scroll) % HOTBAR_SIZE
            self.aim_visible = True
            return
        _, panel_x, panel_width = layout_columns(self.stdscr.getmaxyx()[1])
        if panel_x <= mx < panel_x + panel_width:
            self._stop_mouse_action()
            if fresh_press:
                if 3 <= my < 3 + HOTBAR_SIZE:
                    self.active_inventory_slot = my - 3
                    self.aim_visible = True
                elif my == 18:
                    self._inventory_menu()
                elif my == 19:
                    self.process_key(27)
                elif my == 21:
                    self._craft_menu()
            return
        target = self._mouse_target()
        if target is None:
            self._stop_mouse_action()
            return
        if fresh_press:
            self.aim_visible = True
            item = self._selected_item()
            if self._mouse_down:
                self._mouse_action = (self.active_inventory_slot, item)
                self._next_mouse_action = time.monotonic() + MOUSE_REPEAT_INTERVAL
            self._use_mouse_target(target, item)

    def _pause(self) -> bool:
        self._stop_controls()
        self._paused = True
        self._request_pause(True)
        options = ["Resume", "Save world", "Quit"]
        selected = 0
        renderer = self._terminal_renderer()
        background = self._compose_frame()
        self.stdscr.timeout(50)
        try:
            while True:
                if background.getmaxyx() != self.stdscr.getmaxyx():
                    background = self._compose_frame()
                frame = background.copy()
                width = min(28, frame.columns)
                left, top = max(0, (frame.columns - width) // 2), max(0, (frame.rows - 8) // 2)
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
                if key == curses.KEY_MOUSE:
                    try:
                        _, mx, my, _, state = curses.getmouse()
                    except curses.error:
                        continue
                    if left <= mx < left + width and top + 3 <= my < top + 3 + len(options):
                        selected = my - top - 3
                        if button(state):
                            key = 10
                if key == curses.KEY_UP:
                    selected = max(0, selected - 1)
                elif key == curses.KEY_DOWN:
                    selected = min(len(options) - 1, selected + 1)
                elif key == 27:
                    return True
                elif key in (curses.KEY_ENTER, 10, 13):
                    if selected == 1:
                        self._persist_card_progress()
                        self._send({"save": True})
                        return True
                    if selected == 2:
                        self.quit_to_menu = True
                        return False
                    return True
                if self._stop_event and self._stop_event.is_set():
                    self.quit_to_menu = True
                    return False
        finally:
            self._request_pause(False)
            self.stdscr.timeout(0)
            self._motion_input().reset()
            prediction = getattr(self, "_prediction", None)
            if prediction and self._server_player():
                prediction.resume(self._server_player(), time.monotonic())
            self._paused = False
            curses.flushinp()
            self._dirty = True

    def _inventory_menu(self):
        from ttx.inventory_ui import backpack_frame
        self._stop_controls()
        self._paused = True
        self._request_pause(True)
        renderer = self._terminal_renderer()
        background = self._compose_frame()
        selected = self.active_inventory_slot
        self._sync_inventory()
        original = self.inventory.copy()
        self.stdscr.timeout(50)
        try:
            while True:
                if background.getmaxyx() != self.stdscr.getmaxyx():
                    self.mouse_raw_x = self.mouse_raw_y = None
                    background = self._compose_frame()
                player = self._server_player() or {}
                self._sync_inventory(player)
                frame, targets = backpack_frame(background, self.inventory, player.get("inventory", {}),
                                                selected, self.active_inventory_slot)
                renderer.present(frame)
                key = self.stdscr.getch()
                if key in (27, ord("e"), ord("E")):
                    break
                if key == curses.KEY_MOUSE:
                    try:
                        _, mx, my, _, state = curses.getmouse()
                    except curses.error:
                        continue
                    self.mouse_raw_x, self.mouse_raw_y = mx, my
                    hit = next((index for left, top, right, bottom, index in targets
                                if left <= mx < right and top <= my < bottom), None)
                    if hit is not None:
                        selected = hit
                        if button(state):
                            key = 10
                    else:
                        selected = max(0, min(BACKPACK_SIZE - 1, selected + wheel(state) * 5))
                if key in (curses.KEY_LEFT, curses.KEY_RIGHT, curses.KEY_UP, curses.KEY_DOWN):
                    selected = max(0, min(BACKPACK_SIZE - 1, selected + {
                        curses.KEY_LEFT: -1, curses.KEY_RIGHT: 1, curses.KEY_UP: -5, curses.KEY_DOWN: 5}[key]))
                slot = hotbar_key(key)
                if key in (10, 13, curses.KEY_ENTER):
                    slot = selected if selected < HOTBAR_SIZE else self.active_inventory_slot
                if slot is not None:
                    self.inventory[slot], self.inventory[selected] = self.inventory[selected], self.inventory[slot]
                    self.active_inventory_slot = selected = slot
                    self.aim_visible = True
                if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                    self.quit_to_menu = True
                    break
        finally:
            if self.inventory != original:
                self._send({"inventory_order": self.inventory.copy()})
            self._request_pause(False)
            self.stdscr.timeout(0)
            self._motion_input().reset()
            prediction = getattr(self, "_prediction", None)
            if prediction and self._server_player():
                prediction.resume(self._server_player(), time.monotonic())
            self._paused = False
            curses.flushinp()
            self._dirty = True

    def _request_pause(self, paused: bool):
        self._send({"pause": paused})
        deadline = time.monotonic() + 0.5
        while bool((self._server_player() or {}).get("paused")) != paused:
            if time.monotonic() >= deadline or self.quit_to_menu or (self._stop_event and self._stop_event.is_set()):
                break
            time.sleep(0.005)

    def _fight_adjacent_enemy(self, requested_enemy_id=None):
        if requested_enemy_id is None:
            target_enemy_id, enemy = self._adjacent_enemy()
        else:
            target_enemy_id = requested_enemy_id
            enemy = self.state.get("enemies", {}).get(target_enemy_id)
            if not enemy or not self._in_reach((int(enemy["x"]), int(enemy["y"])), 1):
                return
        if not target_enemy_id or not enemy:
            return
        self._sync_card_rewards()
        enemy_card_id = enemy.get("card_enemy_id", "enemy_giant_rat")
        renderer = self._terminal_renderer()
        battle_requested = False
        battle_started = False
        with ThreadPoolExecutor(max_workers=1) as loader:
            prepared = loader.submit(prepare_card_battle, enemy_card_id, self.card_player_id,
                                     self.card_deck_ids, self.card_hp, self.card_max_hp,
                                     self.card_base_mana)
            self._stop_controls()
            renderer.begin_battle_transition()
            try:
                prediction = getattr(self, "_prediction", None)
                if prediction and not renderer.wait_battle_transition(
                    lambda: int((self._server_player() or {}).get("input_seq", 0)) >= prediction.sequence, 0.5
                ):
                    return
                self._send({"battle": "start", "enemy_id": target_enemy_id})
                battle_requested = True
                if not renderer.wait_battle_transition(
                    lambda: (self._server_player() or {}).get("battle_enemy") == target_enemy_id, 1.0
                ):
                    return
                battle_started = True
                if not renderer.wait_battle_transition(
                    lambda: prepared.done() or bool(self._stop_event and self._stop_event.is_set()), 5.0
                ):
                    raise ValueError("Battle data did not finish loading.")
                if self._stop_event and self._stop_event.is_set():
                    raise ConnectionError("Disconnected from server.")
                game = prepared.result()
                curses.flushinp()
                result = run_card_battle(
                    enemy_id=enemy_card_id,
                    player_id=self.card_player_id,
                    deck_ids=self.card_deck_ids,
                    hp=self.card_hp,
                    max_hp=self.card_max_hp,
                    base_mana=self.card_base_mana,
                    terminal=CardTerminal(renderer, on_pause=self._request_pause, stop_event=self._stop_event),
                    prepared_game=game,
                )
                # Exploration has the same nonlethal retreat rule as Sandbox.
                # Carrying zero HP would make every subsequent battle unusable.
                self.card_hp = max(1, result.hp)
                self.card_max_hp = result.max_hp
                self.card_base_mana = result.base_mana
                self.card_deck_ids = result.deck_ids
                if result.victory:
                    self._send({"attack": True, "enemy_id": target_enemy_id, "defeated": True})
                self._notice = ("Victory!" if result.victory else
                                "Defeated; survived with 1 HP" if result.hp <= 0 else "Battle ended")
                self._notice_until = time.monotonic() + 2.0
            except (OSError, ValueError, TypeError) as exc:
                self._notice = f"Battle ended: {exc}"
                self._notice_until = time.monotonic() + 3.0
                if isinstance(exc, OSError):
                    self.quit_to_menu = True
            finally:
                self._persist_card_progress()
                if battle_requested:
                    self._send({"battle": "end"})
                self.stdscr.timeout(0)
                self._motion_input().reset()
                curses.flushinp()
                if not renderer.battle_transition_active and battle_started:
                    renderer.begin_battle_transition()
                if renderer.battle_transition_active:
                    renderer.complete_battle_transition(self._compose_frame())

    def _persist_card_progress(self):
        if self.card_deck_ids is not None and self.card_hp is not None:
            self._sync_card_rewards()
            self._send({"card_progress": {"hp": max(1, self.card_hp), "max_hp": self.card_max_hp,
                "mana": self.card_base_mana, "deck": self.card_deck_ids,
                "rewards_received": self._card_rewards_received}})

    def _target_tile(self, target):
        override = self.state.get("custom_tiles", {}).get(f"{target[0]},{target[1]}")
        return override["char"] if override else self.game_map.get_tile(*target) if self.game_map else "."

    def _craft_menu(self):
        from ttx.cli import _menu
        self._stop_controls()
        self._paused = True
        self._request_pause(True)
        try:
            while True:
                inventory = (self._server_player() or {}).get("inventory", {})
                options = []
                for recipe, (costs, item, amount, bench) in RECIPES.items():
                    needs = ", ".join(f"{key} {inventory.get(key, 0)}/{count}" for key, count in costs.items())
                    options.append(f"{item} x{amount}: {needs}" + (" [bench]" if bench else ""))
                selected = _menu(self.stdscr, self._terminal_renderer(), "Crafting", options + ["Back"],
                                 (self._server_player() or {}).get("notice") or "Place a workbench; tools require it within 2 tiles")
                if selected == len(options):
                    break
                # Crafting is allowed while paused; the server still validates
                # proximity and consumes all materials atomically.
                self._send({"craft": list(RECIPES)[selected]})
                time.sleep(0.08)
        finally:
            self._request_pause(False)
            self._paused = False
            self.stdscr.timeout(0)
            self._motion_input().reset()
            prediction = getattr(self, "_prediction", None)
            if prediction:
                prediction.resume(self._server_player(), time.monotonic())
            curses.flushinp()
            self._dirty = True

    def _send(self, message: dict):
        try:
            self.sock.sendall((json.dumps(message) + "\n").encode())
        except OSError:
            self.quit_to_menu = True

    def _sync_card_rewards(self, packet=None):
        if getattr(self, "card_deck_ids", None) is None:
            return
        rewards = (self._server_player(packet) or {}).get("cards", [])
        received = getattr(self, "_card_rewards_received", 0)
        self.card_deck_ids.extend(rewards[received:])
        self._card_rewards_received = len(rewards)

    def _my_player(self) -> dict | None:
        players = self.state.get("players", {})
        client_id = self.state.get("client_id")
        if client_id:
            return players.get(client_id)
        return next(iter(players.values()), None) if players else None

    def _camera_offset(self) -> tuple[float, float]:
        max_y, max_x = self.canvas.getmaxyx()
        player = self._my_player()
        if not player:
            return 0, 0
        smooth = getattr(self, "smooth_graphics", True)
        visible_rows = max(1, max_y / (TILE_PIXELS / 4 if smooth else self.scale))
        game_width, _, _ = layout_columns(max_x)
        visible_cols = max(1, game_width / (TILE_PIXELS / 2 if smooth else self.scale))
        width = self.game_map.width if self.game_map else visible_cols
        height = self.game_map.height if self.game_map else visible_rows
        camera = getattr(self, "_camera", None)
        if not isinstance(camera, Camera):
            camera = self._camera = Camera()
        coordinates = player.get("display_position", position(player))
        cx, cy = camera.follow(coordinates, (visible_cols, visible_rows), (width, height),
                               now=getattr(self, "_frame_time", None) if smooth else None)
        return (cx, cy) if smooth else (round(cx), round(cy))

    def _place_block(self, target=None):
        player = self._controlled_player()
        material = self._selected_item()
        if player is None or material not in BLOCKS:
            if player is not None:
                self._notify("Select a block in slots 1-9 / 0")
            return
        dx, dy = self.build_direction
        target = target or (int(player["x"]) + dx, int(player["y"]) + dy)
        if not self._in_reach(target, 2):
            self._notify("Build reach: 2 tiles")
            return
        if (self._server_player() or {}).get("inventory", {}).get(material, 0) <= 0:
            self._notify(f"No {material} left")
            return
        if self._prediction_blocked(*target):
            self._notify("That tile is occupied")
            return
        self._send({"build": True, "x": target[0], "y": target[1], "material": material})

    def _adjacent_enemy(self) -> tuple[str | None, dict | None]:
        player = self._controlled_player()
        if not player:
            return None, None
        px, py = int(player.get("x", 0)), int(player.get("y", 0))
        for enemy_id, enemy in self.state.get("enemies", {}).items():
            ex, ey = int(enemy.get("x", 0)), int(enemy.get("y", 0))
            if abs(ex - px) + abs(ey - py) == 1:
                return enemy_id, enemy
        return None, None

    def _draw_entities(self, camera_x: float, camera_y: float, game_width: int, max_y: int):
        if self._dot_canvas:
            camera = camera_x, camera_y
            for obj in self.state.get("objects", {}).values():
                if obj.get("type") == "tree":
                    tree_sprite(self._dot_canvas, obj, camera, curses.color_pair(2))
                else:
                    actor_sprite(self._dot_canvas, obj, camera, curses.color_pair(4))
            for enemy in self.state.get("enemies", {}).values():
                actor_sprite(self._dot_canvas, enemy, camera, curses.color_pair(5) | curses.A_BOLD)
            for player_id, player in self.state.get("players", {}).items():
                pair = 4 if player_id == self.state.get("client_id") else 3
                actor_sprite(self._dot_canvas, player, camera, curses.color_pair(pair) | curses.A_BOLD)
            return
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
        self._safe_addstr(1, content_x, "Inventory:", panel_width - 3)
        inventory = player.get("inventory", {})
        for index, material in enumerate(self._sync_inventory(player)[:HOTBAR_SIZE]):
            prefix = "->" if index == self.active_inventory_slot else "  "
            label = f"{SYMBOLS.get(material, '?')} {material} x{inventory[material]}" if material else ""
            self._safe_addstr(3 + index, content_x, f"{prefix}{index + 1}: {label}", panel_width - 3)
        hp = self.card_hp if self.card_hp is not None else player.get("hp", 50)
        lines = [f"HP {hp}  Gold {player.get('gold', 0)}", "1-9,0 / wheel: select",
                 "Hold LMB: place / mine", "RMB: hide aim", "[E Backpack: 25 slots]", "[Esc Pause]",
                 "A/D walk  W jump", "[C Crafting]"]
        for row, text in enumerate(lines, 14):
            if row < max_y - 2:
                self._safe_addstr(row, content_x, text, panel_width - 3)
        target = self._mouse_target()
        if target:
            item, tier = TILES.get(self._target_tile(target), ("Air", 0))
            if max_y > 25:
                self._safe_addstr(23, content_x, f"{item} / pick {tier}" if tier else item, panel_width - 3)
        if getattr(self, "_notice", "") and time.monotonic() < self._notice_until:
            self._safe_addstr(max_y - 2, content_x, self._notice, panel_width - 3)

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
    sock.settimeout(5.0)
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
    try:
        from ttx.world.storage import player_identity
        sock.sendall((json.dumps({"hello": player_identity()}) + "\n").encode())
        listener.start()
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
        if listener.ident is not None:
            listener.join()
        sock.close()


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_WHITE, -1)
    curses.init_pair(4, curses.COLOR_CYAN, -1)
    curses.init_pair(5, curses.COLOR_RED, -1)
    curses.init_pair(6, 130 if getattr(curses, "COLORS", 0) >= 256 else curses.COLOR_YELLOW, -1)
    curses.init_pair(7, curses.COLOR_YELLOW, -1)
    curses.init_pair(8, curses.COLOR_BLUE, -1)
    curses.init_pair(9, curses.COLOR_MAGENTA, -1)
    curses.init_pair(10, 240 if getattr(curses, "COLORS", 0) >= 256 else curses.COLOR_BLACK, -1)
    palette = (curses.COLOR_BLACK, curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_YELLOW,
               curses.COLOR_BLUE, curses.COLOR_MAGENTA, curses.COLOR_CYAN, curses.COLOR_WHITE)
    for foreground in range(8):
        for background in range(8):
            curses.init_pair(16 + foreground * 8 + background, palette[foreground], palette[background])
    init_material_colors()

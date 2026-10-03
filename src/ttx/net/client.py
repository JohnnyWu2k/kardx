from __future__ import annotations

import curses
import json
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from ttx.combat.card_battle import prepare_card_battle, run_card_battle
from ttx.input import MotionInput, windows_key_state
from ttx.terminal import CardTerminal, Frame, TerminalRenderer
from ttx.net.prediction import LocalPrediction, RemoteInterpolation
from ttx.net.protocol import SNAPSHOT_LIMIT, JsonLineReader, ProtocolError, valid_snapshot
from ttx.world.camera import Camera
from ttx.world.map import InfiniteGameMap
from ttx.world.physics import position
from ttx.world.render import DotCanvas, actor_sprite, marker, origin, terrain, tree_sprite

PORT = 12345
game_state: dict = {}
UI_WIDTH_RATIO = 0.25
MIN_PANEL_WIDTH = 18
FRAME_INTERVAL = 1 / 60


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
        self._card_rewards_received = 0
        self._dirty = True
        self._last_render = 0.0
        self._renderer = renderer or TerminalRenderer(stdscr)
        self._controls = MotionInput(windows_key_state())
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
        if ch == "v":
            self.smooth_graphics = not self.smooth_graphics
            self._camera = Camera()
            self._dirty = True
            return True
        if ch == "g":
            dx, dy = self.build_direction if self.building_mode_active else (int((self._controlled_player() or {}).get("facing", 1)), 0)
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
        if getattr(self, "_paused", False):
            return
        direction, jumped = (0, False) if self.building_mode_active else self._motion_input().sample(now)
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
        return state

    def _stop_controls(self):
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
        self._render_state = self._view_state(time.monotonic())
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
                    attributes["#"] |= curses.A_DIM
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
        if self.building_mode_active:
            player = self._my_player()
            if player:
                dx, dy = self.build_direction
                aim = {"x": int(player["x"]) + dx, "y": int(player["y"]) + dy, "char": "+"}
                if smooth and self._dot_canvas:
                    marker(self._dot_canvas, aim, (camera_x, camera_y), curses.color_pair(4) | curses.A_BOLD)
                else:
                    self._draw_at(aim, camera_x, camera_y, game_width, max_y, curses.A_REVERSE)
        if self._dot_canvas:
            self._dot_canvas.paint(self.canvas)
        self._draw_divider(game_width, max_y)
        self._draw_ui_panel(panel_x, panel_width, max_y)

    def run(self) -> str:
        if not self.wait_for_map_seed():
            return "quit_to_menu"
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
        self._paused = True
        self._request_pause(True)
        options = ["Resume", "Quit"]
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

    def _fight_adjacent_enemy(self):
        target_enemy_id, enemy = self._adjacent_enemy()
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
                if battle_requested:
                    self._send({"battle": "end"})
                self.stdscr.timeout(0)
                self._motion_input().reset()
                curses.flushinp()
                if not renderer.battle_transition_active and battle_started:
                    renderer.begin_battle_transition()
                if renderer.battle_transition_active:
                    renderer.complete_battle_transition(self._compose_frame())

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
        visible_rows = max(1, max_y / (1 if smooth else self.scale))
        game_width, _, _ = layout_columns(max_x)
        visible_cols = max(1, game_width / (2 if smooth else self.scale))
        width = self.game_map.width if self.game_map else visible_cols
        height = self.game_map.height if self.game_map else visible_rows
        camera = getattr(self, "_camera", None)
        if not isinstance(camera, Camera):
            camera = self._camera = Camera()
        coordinates = player.get("display_position", position(player))
        cx, cy = camera.follow(coordinates, (visible_cols, visible_rows), (width, height))
        return (cx, cy) if smooth else (round(cx), round(cy))

    def _place_block(self):
        player = self._controlled_player()
        material = self.inventory[self.active_inventory_slot]
        if player is None or material is None:
            return
        dx, dy = self.build_direction
        self._send({"build": True, "x": int(player["x"]) + dx,
                    "y": int(player["y"]) + dy, "material": material})

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
        self._safe_addstr(13, content_x, "V smooth / text", panel_width - 3)
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
    curses.init_pair(6, curses.COLOR_YELLOW, -1)
    curses.init_pair(7, curses.COLOR_YELLOW, -1)
    curses.init_pair(8, curses.COLOR_BLUE, -1)
    curses.init_pair(9, curses.COLOR_MAGENTA, -1)

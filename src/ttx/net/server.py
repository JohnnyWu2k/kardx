from __future__ import annotations

import json
import random
import socket
import threading
import time
from collections import deque
from copy import deepcopy

from ttx.world.map import InfiniteGameMap
from ttx.world.physics import INPUT_STEP, grounded, jump, release_motion, request_jump, step_actor, stop_motion
from ttx.net.prediction import apply_input
from ttx.net.protocol import COMMAND_LIMIT, JsonLineReader, ProtocolError, valid_command
from ttx.net.transport import SnapshotWriter
from ttx.world.spawn import object_at, spawn_enemies, spawn_objects

HOST = "0.0.0.0"
PORT = 12345
WORLD_WIDTH = 512
WORLD_HEIGHT = 192
TICK_INTERVAL = 0.05
ENEMY_MOVE_INTERVAL = 0.10  # AI decisions; movement still advances every tick.
CONTROL_TIMEOUT_TICKS = 7
SIGHT_MEMORY_TICKS = 16

players: dict[str, dict] = {}
enemies: dict[str, dict] = {}
objects: dict[str, dict] = {}
custom_tiles: dict[str, dict] = {}
connections: dict[socket.socket, str] = {}
snapshot_writers: dict[socket.socket, SnapshotWriter] = {}
input_queues: dict[str, deque] = {}
state_lock = threading.RLock()
broadcast_lock = threading.Lock()
server_stop_event = threading.Event()
server_socket: socket.socket | None = None
server_verbose = True

map_seed = random.randint(0, 1_000_000)
world_map: InfiniteGameMap | None = None
enemy_rng = random.Random()
enemy_move_elapsed = 0.0
simulation_tick = 0
terrain_revision = 0
server_lifecycle_lock = threading.Lock()
server_runtime = None


class ServerHandle:
    def __init__(self, runtime):
        self.runtime = runtime
        self.thread = runtime.thread

    @property
    def port(self):
        return self.runtime.port

    def stop(self):
        self.runtime.stop()
        self.thread.join()


def build_state(client_id: str | None = None) -> dict:
    with state_lock:
        return deepcopy({
            "client_id": client_id,
            "players": players,
            "enemies": enemies,
            "objects": objects,
            "custom_tiles": custom_tiles,
            "map_seed": map_seed,
            "world_width": world_map.width if world_map else WORLD_WIDTH,
            "world_height": world_map.height if world_map else WORLD_HEIGHT,
            "tick": simulation_tick,
            "terrain_revision": terrain_revision,
            "world_paused": _world_paused(),
        })


def reset_game_state(world_width: int, world_height: int, seed: int | None = None):
    with server_lifecycle_lock:
        if server_runtime is not None and threading.current_thread() is not server_runtime.thread:
            raise RuntimeError("Cannot reset a running TTX server.")
        _reset_game_state(world_width, world_height, seed)


def _reset_game_state(world_width: int, world_height: int, seed: int | None):
    global map_seed, world_map, enemy_rng, enemy_move_elapsed, simulation_tick, terrain_revision
    next_seed = seed if seed is not None else random.randint(0, 1_000_000)
    next_world_map = InfiniteGameMap(max(WORLD_WIDTH, world_width), seed=next_seed,
                                     height=max(WORLD_HEIGHT, world_height))
    next_enemies = spawn_enemies(next_world_map.width, next_world_map.height,
                                 seed=next_seed, game_map=next_world_map)
    next_objects = spawn_objects(next_world_map.width, next_world_map.height,
                                 seed=next_seed, game_map=next_world_map)
    with state_lock:
        players.clear()
        enemies.clear()
        enemies.update(next_enemies)
        objects.clear()
        objects.update(next_objects)
        custom_tiles.clear()
        connections.clear()
        snapshot_writers.clear()
        input_queues.clear()
        map_seed = next_seed
        world_map = next_world_map
        enemy_rng = random.Random(next_seed)
        enemy_move_elapsed = 0.0
        simulation_tick = 0
        terrain_revision = 0


def broadcast_state():
    # Serialize snapshots under the simulation lock, then publish to independent
    # writers. A slow connection must never stall world ticks or other clients.
    with broadcast_lock:
        with state_lock:
            state = build_state()
            state.pop("client_id")
            shared = json.dumps(state, separators=(",", ":"), allow_nan=False).encode()
            payloads = [(snapshot_writers[conn], b'{"client_id":' + json.dumps(client_id).encode() +
                         b"," + shared[1:] + b"\n") for conn, client_id in connections.items()
                        if conn in snapshot_writers]
        for writer, payload in payloads:
            writer.publish(payload)


def tick_world():
    """Advance physics independently of player input; called at 20 Hz."""
    global enemy_move_elapsed, simulation_tick
    with state_lock:
        if world_map is None or _world_paused():
            return
        simulation_tick += 1
        for client_id, player in players.items():
            if player.get("battle_enemy") or player.get("paused"):
                continue
            blocked = lambda x, y, actor=player: _actor_blocked(x, y, actor)
            queue = input_queues.get(client_id)
            if simulation_tick > player.get("move_expires_tick", -1):
                player["move"] = 0
                player["input_mode"] = False
            if queue or player.get("input_mode"):
                # The client and server run the same 60 Hz input frames. Do not
                # add unacknowledged physics between frames: replay must match.
                for _ in range(3):
                    if not queue:
                        break
                    command = queue.popleft()
                    apply_input(player, command, blocked)
                    player["input_seq"] = command["input_seq"]
            else:
                for _ in range(3):
                    step_actor(player, blocked, int(player.get("move", 0)), dt=INPUT_STEP)
            _finish_release(client_id)
        if _world_paused():
            return
        enemy_move_elapsed += TICK_INTERVAL
        if enemy_move_elapsed >= ENEMY_MOVE_INTERVAL:
            enemy_move_elapsed -= ENEMY_MOVE_INTERVAL
            _update_enemies()
        for enemy in enemies.values():
            if not enemy.get("engaged_by"):
                enemy["jump_cooldown"] = max(0, enemy.get("jump_cooldown", 0) - 1)
                speed = 0.30 if enemy.get("mode") == "chase" else 0.22
                for _ in range(3):
                    step_actor(enemy, lambda x, y, actor=enemy: _actor_blocked(x, y, actor),
                               int(enemy.get("move", 0)), speed, dt=INPUT_STEP)


def _world_paused() -> bool:
    return bool(players) and all(player.get("paused") for player in players.values())


def _finish_release(client_id: str):
    player = players[client_id]
    if input_queues.get(client_id):
        return
    if player.pop("release_requested", False):
        release_motion(player)
    if player.pop("pause_requested", False):
        release_motion(player)
        player["paused"] = True


def _handle_pause(client_id: str, paused: bool):
    player = players[client_id]
    if paused:
        player["pause_requested"] = True
        _finish_release(client_id)
    else:
        player.pop("pause_requested", None)
        player.pop("paused", None)
        player["move_expires_tick"] = simulation_tick + CONTROL_TIMEOUT_TICKS


def _queue_input(client_id: str, message: dict):
    player = players[client_id]
    sequence, direction = message.get("input_seq"), message.get("move", 0)
    if type(sequence) is not int or sequence <= player.get("input_received_seq", 0) or direction not in (-1, 0, 1):
        return
    queue = input_queues.setdefault(client_id, deque())
    if len(queue) >= 60:
        return
    command = {"input_seq": sequence, "move": int(direction)}
    if message.get("stop"):
        command["stop"] = True
    if message.get("jump"):
        command["jump"] = True
    queue.append(command)
    player.update(input_received_seq=sequence, input_mode=True,
                  move_expires_tick=simulation_tick + CONTROL_TIMEOUT_TICKS)


def _simulation_loop():
    deadline = time.monotonic() + TICK_INTERVAL
    while not server_stop_event.wait(max(0, deadline - time.monotonic())):
        # Catch up short stalls without making socket/render time slow gravity.
        now = time.monotonic()
        for _ in range(5):
            if deadline > now:
                break
            tick_world()
            deadline += TICK_INTERVAL
        if deadline <= now:
            deadline = now + TICK_INTERVAL
        broadcast_state()


def _has_line_of_sight(observer: dict, target: dict) -> bool:
    """Trace all grid cells crossed by a ray, including solid corner cells."""
    x, y = int(observer["x"]), int(observer["y"])
    tx, ty = int(target["x"]), int(target["y"])
    nx, ny = abs(tx - x), abs(ty - y)
    sx, sy = (tx > x) - (tx < x), (ty > y) - (ty < y)
    ix = iy = 0
    while ix < nx or iy < ny:
        cross_x, cross_y = (1 + 2 * ix) * ny, (1 + 2 * iy) * nx
        if cross_x == cross_y:
            if _terrain_blocked(x + sx, y) or _terrain_blocked(x, y + sy):
                return False
            x, y, ix, iy = x + sx, y + sy, ix + 1, iy + 1
        elif cross_x < cross_y:
            x, ix = x + sx, ix + 1
        else:
            y, iy = y + sy, iy + 1
        if _terrain_blocked(x, y):
            return False
    return True


def _update_enemies():
    decision_ticks = round(ENEMY_MOVE_INTERVAL / TICK_INTERVAL)
    for enemy in enemies.values():
        if enemy.get("engaged_by"):
            enemy["mode"] = "battle"
            continue
        radius = int(enemy.get("aggro_radius", 12))
        candidates = []
        for player_id, player in players.items():
            distance = abs(int(player["x"]) - int(enemy["x"])) + abs(int(player["y"]) - int(enemy["y"]))
            sight_radius = radius + (4 if enemy.get("target_id") == player_id else 0)
            if not player.get("battle_enemy") and not player.get("paused") and not player.get("pause_requested") and distance <= sight_radius and _has_line_of_sight(enemy, player):
                candidates.append((distance, player_id, player))
        if candidates:
            # Keep a visible target rather than twitch between two nearby players.
            distance, target_id, target = next(
                (item for item in candidates if item[1] == enemy.get("target_id")),
                min(candidates, key=lambda item: item[0]),
            )
            enemy.update(mode="chase", target_id=target_id, memory_ticks=SIGHT_MEMORY_TICKS,
                         last_seen_x=int(target["x"]), last_seen_y=int(target["y"]))
        elif (enemy.get("memory_ticks", 0) > 0 and
              enemy.get("target_id") in players and
              not players[enemy["target_id"]].get("battle_enemy") and
              not players[enemy["target_id"]].get("paused") and
              abs(int(players[enemy["target_id"]]["x"]) - int(enemy["x"])) +
              abs(int(players[enemy["target_id"]]["y"]) - int(enemy["y"])) <= radius + 4):
            enemy["memory_ticks"] -= decision_ticks
            enemy["mode"] = "search"
            target = {"x": enemy["last_seen_x"], "y": enemy["last_seen_y"]}
            distance = abs(int(target["x"]) - int(enemy["x"])) + abs(int(target["y"]) - int(enemy["y"]))
        else:
            enemy.update(mode="patrol", memory_ticks=0)
            enemy.pop("target_id", None)
            target, distance = None, 9999
        pursuing = enemy["mode"] in ("chase", "search")
        if pursuing:
            if distance <= 1:
                enemy.update(move=0, vx=0.0, horizontal_progress=0.0)
                continue  # Stay adjacent so the player can enter card combat.
            delta = int(target["x"]) - int(enemy["x"])
            direction = (delta > 0) - (delta < 0)
        else:
            direction = int(enemy.get("direction", 1))
            home_delta = int(enemy.get("home_x", enemy["x"])) - int(enemy["x"])
            waiting = enemy.get("patrol_wait_ticks", 0)
            if waiting > 0:
                enemy["patrol_wait_ticks"] = max(0, waiting - decision_ticks)
                enemy["move"] = 0
                continue
            if abs(home_delta) > 14:
                direction = 1 if home_delta > 0 else -1
            elif (float(enemy.get("vy", 0)) >= 0 and grounded(enemy, lambda x, y: _terrain_blocked(x, y))
                  and enemy_rng.random() < 0.025):
                direction *= -1
                enemy["patrol_wait_ticks"] = enemy_rng.randint(3, 8)
                enemy["direction"], enemy["move"] = direction, 0
                continue
        enemy["direction"] = direction or int(enemy.get("direction", 1)) or 1
        ex, ey = int(enemy["x"]), int(enemy["y"])
        blocked = lambda x, y, actor=enemy: _actor_blocked(x, y, actor)
        on_ground = grounded(enemy, blocked) and float(enemy.get("vy", 0)) >= 0
        if direction == 0:
            enemy["move"] = 0
            if pursuing and int(target["y"]) < ey and not enemy.get("jump_cooldown"):
                jump(enemy, blocked)
                enemy["jump_cooldown"] = 8
            continue
        nx = ex + direction
        obstacle = _terrain_blocked(nx, ey)
        ledge = not _terrain_blocked(nx, ey + 1)
        if on_ground and not enemy.get("jump_cooldown") and (obstacle or (pursuing and (ledge or int(target["y"]) < ey - 1))):
            if not blocked(ex, ey - 1) and any(not _terrain_blocked(nx, ey - rise) for rise in range(1, 5)):
                if jump(enemy, blocked):
                    enemy["jump_cooldown"] = 8
        enemy["move"] = direction if pursuing or not on_ground or not ledge or float(enemy.get("vy", 0)) < 0 else 0
        if not pursuing and (obstacle and float(enemy.get("vy", 0)) >= 0 or on_ground and ledge):
            enemy["direction"] *= -1
            enemy["patrol_wait_ticks"] = 2
            enemy["move"] = 0


def handle_client(conn: socket.socket, addr):
    if server_stop_event.is_set():
        conn.close()
        return
    try:
        conn.settimeout(0.2)
    except OSError:
        conn.close()
        return
    try:
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass
    client_id = str(addr)
    writer = SnapshotWriter(conn)
    _log(f"[SERVER] New connection from {client_id}")
    with state_lock:
        if server_stop_event.is_set():
            conn.close()
            return
        spawn = _player_spawn()
        if spawn is None:
            conn.close()
            return
        spawn_x, spawn_y = spawn
        players[client_id] = {
            "x": spawn_x,
            "y": spawn_y,
            "char": "@",
            "hp": 50,
            "inventory": {},
            "cards": [],
            "facing": 1,
            "vy": 0.0,
            "vertical_progress": 0.0,
            "vx": 0.0,
            "horizontal_progress": 0.0,
            "move": 0,
            "input_seq": 0,
        }
        connections[conn] = client_id
        snapshot_writers[conn] = writer
    reader = JsonLineReader(COMMAND_LIMIT)
    try:
        writer.start()
        broadcast_state()
        while not server_stop_event.is_set():
            try:
                data = conn.recv(4096)
            except socket.timeout:
                continue
            if not data:
                break
            for message in reader.feed(data):
                if not valid_command(message):
                    continue
                if message.get("disconnect"):
                    return
                process_message(client_id, message)
    except (ConnectionAbortedError, ConnectionResetError, OSError):
        pass
    except ProtocolError as exc:
        _log(f"[SERVER] Error processing {client_id}: {exc}")
    finally:
        with state_lock:
            _log(f"[SERVER] Connection closed: {client_id}")
            connections.pop(conn, None)
            snapshot_writers.pop(conn, None)
            _end_battle(client_id)
            players.pop(client_id, None)
            input_queues.pop(client_id, None)
        writer.close()
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        if writer.thread.ident is not None:
            writer.thread.join()
        conn.close()
        broadcast_state()


def _player_spawn() -> tuple[int, int] | None:
    if world_map is None:
        return (5, 21) if not _is_occupied(5, 21) else None
    start_x, _ = world_map.spawn_position()
    for offset in range(world_map.width):
        x = (start_x + offset) % world_map.width
        y = world_map.surface_height(x) - 1
        if not _is_blocked(x, y):
            return x, y
    return None


def process_message(client_id: str, message: dict):
    if not valid_command(message):
        return
    with state_lock:
        if client_id not in players or world_map is None:
            return
        if "pause" in message and type(message["pause"]) is bool:
            _handle_pause(client_id, message["pause"])
        elif message.get("battle") == "end":
            _end_battle(client_id)
        elif players[client_id].get("paused") or players[client_id].get("pause_requested"):
            return
        elif message.get("battle"):
            _handle_battle(client_id, message)
        elif players[client_id].get("battle_enemy") and not message.get("attack"):
            return
        elif message.get("build"):
            _handle_build(client_id, message)
        elif message.get("attack"):
            _handle_attack(client_id, message)
        elif message.get("gather"):
            _handle_gather(client_id, message)
        elif "input_seq" in message:
            _queue_input(client_id, message)
        else:
            if message.get("stop"):
                players[client_id]["release_requested"] = True
                _finish_release(client_id)
                return
            if "move" in message or "dx" in message:
                _handle_move(client_id, message.get("move", message.get("dx", 0)))
            if message.get("jump"):
                request_jump(players[client_id], lambda x, y: _actor_blocked(x, y, players[client_id]))


def _handle_build(client_id: str, message: dict):
    global terrain_revision
    player = players[client_id]
    x = int(message.get("x", 0))
    y = int(message.get("y", 0))
    material = str(message.get("material", "wood"))
    inventory = player.setdefault("inventory", {})
    blocks = {"wood": "|", "stone": "#", "dirt": ":", "sand": "%"}
    if material not in blocks or int(inventory.get(material, 0)) <= 0:
        return
    block = blocks[material]
    if abs(x - int(player["x"])) + abs(y - int(player["y"])) > 2 or not _can_build_at(x, y):
        return
    custom_tiles[f"{x},{y}"] = {"x": x, "y": y, "block": block, "char": block}
    terrain_revision += 1
    inventory[material] -= 1


def _handle_attack(client_id: str, message: dict):
    player = players[client_id]
    target_enemy_id = message.get("enemy_id") or _adjacent_enemy_id(player)
    if not target_enemy_id or target_enemy_id not in enemies:
        return
    enemy = enemies[target_enemy_id]
    if enemy.get("engaged_by") != client_id or player.get("battle_enemy") != target_enemy_id:
        return
    if message.get("defeated"):
        _grant_enemy_rewards(player, enemy)
        del enemies[target_enemy_id]
        player.pop("battle_enemy", None)
        return
    enemy["hp"] = int(enemy.get("hp", 1)) - int(message.get("damage", 0))
    if enemy["hp"] <= 0:
        _grant_enemy_rewards(player, enemy)
        del enemies[target_enemy_id]
        player.pop("battle_enemy", None)


def _handle_gather(client_id: str, message: dict | None = None):
    global terrain_revision
    player = players[client_id]
    px, py = int(player["x"]), int(player["y"])
    message = message or {}
    dx, dy = int(message.get("dx", player.get("facing", 1))), int(message.get("dy", 0))
    if abs(dx) + abs(dy) != 1:
        return
    positions = [(px, py), (px + dx, py + dy)]
    found = object_at(objects, positions)
    if found:
        object_id, obj = found
        drop = obj.get("drop", obj.get("type", "material"))
        del objects[object_id]
    else:
        x, y = px + dx, py + dy
        if world_map is None or x <= 0 or x >= world_map.width - 1 or y >= world_map.height - 1:
            return
        tile = _tile_at(x, y)
        if tile not in InfiniteGameMap.SOLID_TILES:
            return
        drop = {"*": "crystal_shard", "o": "stone", "|": "wood", ":": "dirt", '"': "dirt", "%": "sand"}.get(tile, "stone")
        custom_tiles[f"{x},{y}"] = {"x": x, "y": y, "char": ".", "block": "."}
        terrain_revision += 1
    inventory = player.setdefault("inventory", {})
    inventory[drop] = int(inventory.get(drop, 0)) + 1


def _handle_move(client_id: str, dx: int, dy: int = 0):
    if dx not in (-1, 0, 1):
        return
    player = players[client_id]
    player["move"] = int(dx)
    player["move_expires_tick"] = simulation_tick + CONTROL_TIMEOUT_TICKS
    if dx:
        player["facing"] = int(dx)


def _can_build_at(x: int, y: int) -> bool:
    if _terrain_blocked(x, y):
        return False
    return not _is_occupied(x, y)


def _is_blocked(x: int, y: int) -> bool:
    if _terrain_blocked(x, y):
        return True
    return _is_occupied(x, y)


def _is_occupied(x: int, y: int) -> bool:
    for player in players.values():
        if int(player.get("x", -1)) == x and int(player.get("y", -1)) == y:
            return True
    for enemy in enemies.values():
        if int(enemy.get("x", -1)) == x and int(enemy.get("y", -1)) == y:
            return True
    return False  # Trees are gatherable foreground decoration, not solid actors.


def _tile_at(x: int, y: int) -> str:
    if world_map is None or not (0 <= x < world_map.width and 0 <= y < world_map.height):
        return " "
    override = custom_tiles.get(f"{x},{y}")
    return override["char"] if override else world_map.get_tile(x, y)


def _terrain_blocked(x: int, y: int) -> bool:
    return _tile_at(x, y) != InfiniteGameMap.AIR


def _actor_blocked(x: int, y: int, actor: dict) -> bool:
    if _terrain_blocked(x, y):
        return True
    return any(other is not actor and int(other["x"]) == x and int(other["y"]) == y
               for other in (*players.values(), *enemies.values()))


def _handle_battle(client_id: str, message: dict):
    if message.get("battle") == "end":
        _end_battle(client_id)
        return
    enemy_id = message.get("enemy_id")
    player = players[client_id]
    enemy = enemies.get(enemy_id)
    if message.get("battle") != "start" or player.get("battle_enemy") or not enemy or enemy.get("engaged_by"):
        return
    if abs(int(player["x"]) - int(enemy["x"])) + abs(int(player["y"]) - int(enemy["y"])) != 1:
        return
    player["battle_enemy"] = enemy_id
    enemy["engaged_by"] = client_id
    enemy["mode"] = "battle"
    stop_motion(player)
    stop_motion(enemy)
    input_queues.pop(client_id, None)
    player["input_seq"] = player.get("input_received_seq", player.get("input_seq", 0))


def _end_battle(client_id: str):
    player = players.get(client_id)
    if player:
        player.pop("battle_enemy", None)
    for enemy in enemies.values():
        if enemy.get("engaged_by") == client_id:
            enemy.pop("engaged_by", None)
            enemy["mode"] = "patrol"


def _adjacent_enemy_id(player: dict) -> str | None:
    px, py = int(player.get("x", 0)), int(player.get("y", 0))
    for enemy_id, enemy in enemies.items():
        ex, ey = int(enemy.get("x", 0)), int(enemy.get("y", 0))
        if abs(ex - px) + abs(ey - py) == 1:
            return enemy_id
    return None


def _grant_enemy_rewards(player: dict, enemy: dict):
    player["gold"] = int(player.get("gold", 0)) + int(enemy.get("gold", 5))
    reward_cards = enemy.get("reward_cards") or []
    if reward_cards:
        player.setdefault("cards", []).append(random.choice(reward_cards))


class _ServerRuntime:
    """Own the listener and every worker until shutdown has completed."""

    def __init__(self, width: int, height: int, verbose: bool, host: str, port: int):
        self.width, self.height, self.verbose = width, height, verbose
        self.host, self.port = host, port
        self.ready = threading.Event()
        self.error: Exception | None = None
        self.socket: socket.socket | None = None
        self.clients = set()
        self.handlers = set()
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, name="ttx-server", daemon=False)

    def stop(self):
        with server_lifecycle_lock:
            # A handle from an earlier session must not stop a new host.
            if server_runtime is not self:
                return
            server_stop_event.set()
            with self.lock:
                clients = list(self.clients)
        for connection in clients:
            _shutdown_connection(connection)

    def _handle(self, connection, address):
        try:
            handle_client(connection, address)
        finally:
            connection.close()
            with self.lock:
                self.clients.discard(connection)
                self.handlers.discard(threading.current_thread())

    def _simulate(self):
        try:
            _simulation_loop()
        except Exception as exc:
            self.error = exc
            self.stop()

    def _run(self):
        global server_socket, server_verbose, server_runtime
        simulation = None
        try:
            server_verbose = self.verbose
            listener = self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket = listener
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((self.host, self.port))
            self.port = listener.getsockname()[1]
            listener.listen(5)
            listener.settimeout(0.2)
            reset_game_state(self.width, self.height)
            simulation = threading.Thread(target=self._simulate, name="ttx-simulation", daemon=False)
            simulation.start()
            self.ready.set()
            _log(f"[SERVER] Listening on port {self.port} with map seed: {map_seed}")
            while not server_stop_event.is_set():
                try:
                    connection, address = listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if server_stop_event.is_set():
                        break
                    raise
                with self.lock:
                    if server_stop_event.is_set():
                        connection.close()
                        break
                    handler = threading.Thread(target=self._handle, args=(connection, address),
                                               name="ttx-client", daemon=False)
                    self.clients.add(connection)
                    self.handlers.add(handler)
                    try:
                        handler.start()
                    except Exception:
                        self.clients.discard(connection)
                        self.handlers.discard(handler)
                        connection.close()
                        raise
        except Exception as exc:
            self.error = exc
        finally:
            self.stop()
            if self.socket is not None:
                self.socket.close()
            self.ready.set()
            if simulation is not None:
                simulation.join()
            with self.lock:
                handlers = list(self.handlers)
            for handler in handlers:
                handler.join()
            with server_lifecycle_lock:
                server_socket = None
                if server_runtime is self:
                    server_runtime = None


def _shutdown_connection(connection):
    try:
        connection.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


def server_main(world_width: int, world_height: int, verbose: bool = True):
    handle = start_server(world_width, world_height, verbose)
    try:
        handle.thread.join()
    finally:
        handle.stop()
    if handle.runtime.error is not None:
        raise handle.runtime.error


def start_server(world_width: int, world_height: int, verbose: bool = True,
                 *, host: str = HOST, port: int = PORT) -> ServerHandle:
    global server_runtime
    with server_lifecycle_lock:
        if server_runtime is not None:
            raise RuntimeError("A TTX server is already running in this process.")
        runtime = _ServerRuntime(world_width, world_height, verbose, host, port)
        server_runtime = runtime
        server_stop_event.clear()
        try:
            runtime.thread.start()
        except Exception:
            server_runtime = None
            raise
    if not runtime.ready.wait(5.0):
        runtime.stop()
        runtime.thread.join()
        raise TimeoutError("TTX server did not become ready.")
    if runtime.error is not None:
        runtime.thread.join()
        raise runtime.error
    return ServerHandle(runtime)


def stop_server():
    runtime = server_runtime
    if runtime is not None:
        ServerHandle(runtime).stop()
        return
    server_stop_event.set()
    with state_lock:
        clients = list(connections)
    for connection in clients:
        _shutdown_connection(connection)


def _log(message: str):
    if server_verbose:
        print(message)

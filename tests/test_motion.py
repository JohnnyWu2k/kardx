"""Regression coverage for latency, fractional graphics, and real simulation pause."""

import copy
import random
import unittest
import curses
from collections import deque
from contextlib import ExitStack
from unittest.mock import patch

from ttx.net import client, server
from ttx.net.prediction import LocalPrediction, RemoteInterpolation, apply_input
from ttx.terminal import Frame
from ttx.world.camera import Camera
from ttx.world.physics import INPUT_INTERVAL, INPUT_STEP, position, step_actor
from ttx.world.render import DotCanvas, actor_sprite, project, terrain


class FlatMap:
    width, height = 512, 192
    AIR = "."
    SOLID_TILES = {"#"}

    def get_tile(self, x, y):
        if not (0 < x < self.width - 1 and 0 <= y < self.height - 1):
            return "#"
        return "#" if y >= 22 else self.AIR

    def _tile_attr(self, tile):
        return 0


class SimulationFixture(unittest.TestCase):
    def setUp(self):
        self.context = ExitStack()
        self.addCleanup(self.context.close)
        self.context.enter_context(patch.object(server, "world_map", FlatMap()))
        self.context.enter_context(patch.object(server, "simulation_tick", 0))
        self.context.enter_context(patch.object(server, "enemy_move_elapsed", 0.0))
        self.context.enter_context(patch.object(server, "enemy_rng", random.Random(1)))
        self.context.enter_context(patch.dict(server.players, {"p": {"x": 100, "y": 21, "input_seq": 0}}, clear=True))
        for name in ("enemies", "objects", "custom_tiles", "input_queues", "connections"):
            self.context.enter_context(patch.dict(getattr(server, name), {}, clear=True))

    def ticks(self, count):
        for _ in range(count):
            server.tick_world()


class PredictionTests(SimulationFixture):
    def test_moves_before_any_reply_and_matches_delayed_server_without_pullback(self):
        predictor = LocalPrediction(server.players["p"], 0.0)
        blocked = lambda x, y: server.world_map.get_tile(x, y) != "."
        outbound, inbound = deque(), deque()
        for frame in range(1, 181):
            now = frame * INPUT_INTERVAL
            while inbound and inbound[0][0] <= frame:
                _, snapshot = inbound.popleft()
                before = position(predictor.actor)
                predictor.reconcile(snapshot, snapshot, blocked)
                for old, new in zip(before, position(predictor.actor)):
                    self.assertAlmostEqual(old, new, places=9, msg=f"correction at frame {frame}")
            direction = 1 if frame <= 90 else 0 if frame <= 105 else -1
            predictor.advance(now, direction, frame == 30, blocked,
                              lambda command: outbound.append((frame + 4, command)))
            if frame == 1:
                self.assertGreater(position(predictor.actor)[0], 100)
                self.assertEqual(position(server.players["p"])[0], 100)
            while outbound and outbound[0][0] <= frame:
                _, command = outbound.popleft()
                server.process_message("p", command)
            if frame % 3 == 0:
                server.tick_world()
                inbound.append((frame + 4, copy.deepcopy(server.players["p"])))
        while outbound:
            _, command = outbound.popleft()
            server.process_message("p", command)
        while server.input_queues["p"]:
            server.tick_world()
        self.assertEqual(server.players["p"]["input_seq"], predictor.sequence)
        for predicted, actual in zip(position(predictor.actor), position(server.players["p"])):
            self.assertAlmostEqual(predicted, actual, places=9)

    def test_release_is_replayed_at_its_input_sequence_before_build_idle_frames(self):
        predictor = LocalPrediction(server.players["p"], 0.0)
        blocked = lambda x, y: server.world_map.get_tile(x, y) != "."
        messages = []
        predictor.advance(INPUT_INTERVAL * 6, 1, False, blocked, messages.append)
        stopped = position(predictor.actor)
        messages.append(predictor.release(INPUT_INTERVAL * 6))
        predictor.advance(INPUT_INTERVAL * 9, 0, False, blocked, messages.append)
        self.assertEqual(position(predictor.actor), stopped)
        for command in messages:
            server.process_message("p", command)
        for _ in range(4):
            server.tick_world()
            snapshot = copy.deepcopy(server.players["p"])
            predictor.reconcile(snapshot, snapshot, blocked)
            self.assertEqual(position(predictor.actor), stopped)
            self.assertEqual(predictor.actor["vx"], 0)
        self.assertEqual(position(server.players["p"]), stopped)

    def test_stalled_client_does_not_emit_a_burst_and_reserves_a_stop_slot(self):
        predictor = LocalPrediction(server.players["p"], 0.0)
        messages = []
        blocked = lambda x, y: y >= 22
        predictor.advance(10.0, 1, False, blocked, messages.append)
        self.assertEqual(len(messages), 1)
        for frame in range(1, 100):
            predictor.advance(10.0 + frame * INPUT_INTERVAL, 1, False, blocked, messages.append)
        self.assertEqual(len(predictor.pending), 59)
        self.assertTrue(predictor.release(12.0)["stop"])
        self.assertEqual(len(predictor.pending), 60)
        self.assertIsNone(predictor.release(12.0))

    def test_server_limits_input_frames_and_does_not_double_simulate_between_them(self):
        for sequence in range(1, 13):
            server.process_message("p", {"input_seq": sequence, "move": 1})
        server.process_message("p", {"input_seq": 12, "move": -1})
        server.process_message("p", {"input_seq": 13, "move": 500})
        self.ticks(1)
        self.assertEqual(server.players["p"]["input_seq"], 3)
        self.ticks(3)
        self.assertEqual(server.players["p"]["input_seq"], 12)
        stopped = position(server.players["p"])
        self.ticks(1)
        self.assertEqual(position(server.players["p"]), stopped)

    def test_timeout_does_not_strand_queued_inputs_or_a_pause_request(self):
        for sequence in range(1, 31):
            server.process_message("p", {"input_seq": sequence, "move": 1})
        server.process_message("p", {"pause": True})
        self.ticks(12)
        self.assertTrue(server.players["p"]["paused"])
        self.assertEqual(server.players["p"]["input_seq"], 30)
        self.assertFalse(server.input_queues["p"])


class PauseTests(SimulationFixture):
    def test_single_player_pause_freezes_air_motion_enemies_and_world_time(self):
        server.players["p"].update(y=15, vertical_progress=0.2, vy=-0.7,
                                   horizontal_progress=0.3, vx=0.42, move=1)
        server.enemies["e"] = {"x": 110, "y": 21, "move": -1, "direction": -1, "jump_cooldown": 4}
        server.process_message("p", {"pause": True})
        before = copy.deepcopy(server.build_state())
        elapsed = server.enemy_move_elapsed
        self.ticks(100)
        self.assertEqual(server.build_state(), before)
        self.assertEqual(server.enemy_move_elapsed, elapsed)
        self.assertTrue(before["world_paused"])
        server.process_message("p", {"move": -1, "jump": True})
        server.process_message("p", {"gather": True, "dx": 0, "dy": 1})
        self.assertEqual(server.build_state(), before)
        server.process_message("p", {"pause": False})
        self.ticks(1)
        self.assertLess(position(server.players["p"])[1], 15.2)
        self.assertEqual(position(server.players["p"])[0], 100.3)
        self.assertEqual(server.simulation_tick, 1)

    def test_pause_drains_predicted_frames_and_preserves_fractional_location(self):
        expected = dict(server.players["p"])
        blocked = lambda x, y: y >= 22
        for sequence in range(1, 6):
            command = {"input_seq": sequence, "move": 1, "jump": sequence == 1}
            apply_input(expected, command, blocked)
            server.process_message("p", command)
        server.process_message("p", {"input_seq": 6, "move": 0, "stop": True})
        server.process_message("p", {"pause": True})
        self.assertFalse(server.players["p"].get("paused"))
        self.ticks(2)
        self.assertTrue(server.players["p"]["paused"])
        self.assertEqual(position(server.players["p"]), position(expected))
        self.assertEqual(server.players["p"]["vy"], expected["vy"])
        before = copy.deepcopy(server.players["p"])
        self.ticks(100)
        self.assertEqual(server.players["p"], before)

    def test_multiplayer_pause_freezes_only_paused_actor_and_ignores_it_as_a_target(self):
        server.players["q"] = {"x": 120, "y": 21, "move": 1}
        server.enemies["e"] = {"x": 103, "y": 21, "move": 0, "direction": 1,
                               "home_x": 103, "mode": "chase", "target_id": "p",
                               "memory_ticks": 16, "last_seen_x": 100, "last_seen_y": 21}
        server.process_message("p", {"pause": True})
        frozen = copy.deepcopy(server.players["p"])
        server.process_message("q", {"move": 1})
        self.ticks(5)
        self.assertEqual(server.players["p"], frozen)
        self.assertGreater(position(server.players["q"])[0], 120)
        self.assertFalse(server._world_paused())
        self.assertNotEqual(server.enemies["e"].get("target_id"), "p")
        server.process_message("q", {"pause": True})
        tick = server.simulation_tick
        self.ticks(10)
        self.assertEqual(server.simulation_tick, tick)
        server.process_message("q", {"pause": False})
        self.ticks(1)
        self.assertEqual(server.simulation_tick, tick + 1)


class FractionalMotionTests(unittest.TestCase):
    def test_cell_crossings_and_braking_never_pull_motion_backwards(self):
        actor = {"x": 5, "y": 21, "horizontal_progress": -0.3}
        blocked = lambda x, y: x <= 4 or y >= 22
        previous = position(actor)[0]
        for frame in range(90):
            step_actor(actor, blocked, 1 if frame < 60 else 0, dt=INPUT_STEP)
            current = position(actor)[0]
            self.assertGreaterEqual(current, previous)
            self.assertLessEqual(current - previous, 0.42 * INPUT_STEP + 1e-9)
            previous = current
        self.assertEqual(actor["vx"], 0)

    def test_substeps_preserve_position_and_velocity_for_the_same_elapsed_time(self):
        for actor, blocked in [({"x": 10, "y": 21}, lambda x, y: y >= 22),
                               ({"x": 10, "y": 15, "vy": -1.5}, lambda x, y: y >= 50)]:
            full, split = dict(actor), dict(actor)
            step_actor(full, blocked, 1)
            for _ in range(3):
                step_actor(split, blocked, 1, dt=INPUT_STEP)
            for a, b in zip(position(full), position(split)):
                self.assertAlmostEqual(a, b, places=9)
            self.assertAlmostEqual(full["vx"], split["vx"], places=9)
            self.assertAlmostEqual(full["vy"], split["vy"], places=9)


class CameraAndGraphicsTests(unittest.TestCase):
    def test_camera_is_fixed_until_edge_and_does_not_flip_on_small_reversal(self):
        camera = Camera()
        initial = camera.follow((100, 21), (40, 30), (512, 192))
        for x in (101, 110, 118.9, 90, 100):
            self.assertEqual(camera.follow((x, 21), (40, 30), (512, 192)), initial)
        shifted = camera.follow((119, 21), (40, 30), (512, 192))
        self.assertGreater(shifted[0], initial[0])
        for x in (119.1, 118.9, 120, 130):
            self.assertEqual(camera.follow((x, 21), (40, 30), (512, 192)), shifted)
        self.assertEqual(camera.follow((511, 191), (40, 30), (512, 192)), (472, 162))
        self.assertEqual(camera.follow((0, 0), (40, 30), (512, 192)), (0, 0))

    def test_player_and_camera_share_projection_without_cell_crossing_jitter(self):
        previous = None
        for phase in range(24):
            x = 100 + phase / 4
            actor = {"x": round(x), "y": 21, "horizontal_progress": x - round(x)}
            projected = project(actor, (x - 20, 6))
            if previous:
                self.assertEqual(projected, previous)
            previous = projected

    @patch.object(curses, "color_pair", return_value=0)
    def test_quarter_tile_changes_sprite_without_crossing_integer_cell(self, _colors):
        first, second = DotCanvas(5, 12), DotCanvas(5, 12)
        actor_sprite(first, {"x": 2, "y": 2}, (0, 0), 4)
        actor_sprite(second, {"x": 2, "y": 2, "horizontal_progress": 0.25}, (0, 0), 4)
        self.assertNotEqual(first.pixels, second.pixels)
        before, after = Frame(5, 12), Frame(5, 12)
        first.paint(before)
        second.paint(after)
        self.assertNotEqual(before.cells, after.cells)

    @patch.object(curses, "color_pair", return_value=0)
    def test_terrain_scrolls_one_dot_and_mining_is_visible(self, _colors):
        game_map = FlatMap()
        first, second = DotCanvas(6, 24), DotCanvas(6, 24)
        tiles = {"3,1": {"char": "#"}}
        terrain(first, game_map, (0, 0), tiles, {"#": 7})
        terrain(second, game_map, (0.125, 0), tiles, {"#": 7})

        def dots(canvas):
            return {(x, y) for y in range(canvas.rows * 4) for x in range(canvas.columns * 2)
                    if canvas.pixels[y // 4][x // 2][(y % 4) * 2 + x % 2] >= 0}

        # Ignore the left world boundary; isolate one fully opaque tile.
        tile = {(x, y) for x, y in dots(first) if 24 <= x <= 31 and 8 <= y <= 15}
        self.assertEqual(len(tile), 64)  # No artificial black seams or shadow holes.
        self.assertEqual({(x - 1, y) for x, y in tile},
                         {(x, y) for x, y in dots(second) if 23 <= x <= 30 and 8 <= y <= 15})
        mined = DotCanvas(6, 24)
        terrain(mined, game_map, (0, 0), {"3,1": {"char": "."}}, {"#": 7})
        self.assertFalse(any(24 <= x <= 31 and 8 <= y <= 15 for x, y in dots(mined)))

    def test_remote_snapshots_interpolate_instead_of_teleporting(self):
        interpolation = RemoteInterpolation()
        interpolation.update({"players": {}, "enemies": {"e": {"x": 10, "y": 21}}, "received_at": 0.0}, 0.0)
        interpolation.update({"players": {}, "enemies": {"e": {"x": 11, "y": 21}}, "received_at": 0.05}, 0.05)
        self.assertEqual(interpolation.positions(0.05)["enemies", "e"], (10.0, 21.0))
        self.assertAlmostEqual(interpolation.positions(0.075)["enemies", "e"][0], 10.5)
        self.assertEqual(interpolation.positions(0.10)["enemies", "e"], (11.0, 21.0))


class Screen:
    def __init__(self, rows=30, columns=120):
        self.rows, self.columns = rows, columns
        self.writes = []
        self.cells = {}
        self.keys = deque()
        self.on_key = None

    def getmaxyx(self):
        return self.rows, self.columns

    def addstr(self, y, x, text, attr=0):
        self.writes.append((y, x, text, attr))
        for index, char in enumerate(text):
            assert 0 <= y < self.rows and 0 <= x + index < self.columns
            self.cells[y, x + index] = char, attr

    def refresh(self):
        pass

    def nodelay(self, enabled):
        pass

    def keypad(self, enabled):
        pass

    def timeout(self, delay):
        pass

    def getch(self):
        key = self.keys.popleft() if self.keys else -1
        if self.on_key:
            self.on_key(key)
        return key


class ClientGraphicsTests(unittest.TestCase):
    def setUp(self):
        self.context = ExitStack()
        self.addCleanup(self.context.close)
        self.context.enter_context(patch.object(client, "game_state", {
            "client_id": "p", "players": {"p": {"x": 100, "y": 21, "input_seq": 0}},
            "enemies": {}, "objects": {}, "terrain_revision": 0,
        }))
        for name in ("curs_set", "mousemask", "set_escdelay", "flushinp"):
            self.context.enter_context(patch.object(client.curses, name, create=True))
        self.context.enter_context(patch.object(client.curses, "color_pair", return_value=0))
        self.context.enter_context(patch.object(client, "windows_key_state", return_value=None))
        self.screen = Screen()
        self.game = client.Game(self.screen, None)
        self.game.game_map = FlatMap()
        self.messages = []
        self.game._send = self.messages.append

    def test_default_graphics_show_fractional_motion_and_only_repaint_changed_cells(self):
        with patch.object(client, "terrain", wraps=terrain) as draw:
            self.game.render()
            before = self.game._renderer.last.copy()
            self.screen.writes.clear()
            self.game.render()
            self.assertEqual(self.screen.writes, [])
            packet = copy.deepcopy(client.game_state)
            packet["players"]["p"]["horizontal_progress"] = 0.25
            client.game_state = packet
            self.game.render()
            self.assertNotEqual(before.cells, self.game._renderer.last.cells)
            self.assertLessEqual(sum(len(call[2]) for call in self.screen.writes), 16)
            self.assertEqual(draw.call_count, 1)
            self.assertNotIn("display_position", packet["players"]["p"])
            packet = copy.deepcopy(packet)
            packet.update(custom_tiles={"101,22": {"char": "."}}, terrain_revision=1)
            client.game_state = packet
            self.game.render()
            self.assertEqual(draw.call_count, 2)

    def test_graphics_fit_small_viewports_and_toggle_preserves_prediction(self):
        for rows, columns in [(1, 1), (10, 20), (24, 80)]:
            self.screen.rows, self.screen.columns = rows, columns
            self.game.render()
        before = position(self.game._prediction.actor)
        self.assertTrue(self.game.smooth_graphics)
        self.game.process_key(ord("v"))
        self.assertFalse(self.game.smooth_graphics)
        self.assertEqual(position(self.game._prediction.actor), before)
        self.game.process_key(ord("v"))
        self.assertTrue(self.game.smooth_graphics)

    def test_page_switch_rebuilds_terrain_once_then_reuses_it(self):
        with patch.object(client, "terrain", wraps=terrain) as draw:
            self.game.render()
            start = self.game._display_camera
            game_width, _, _ = client.layout_columns(self.screen.columns)
            edge = start[0] + game_width / 4 - 1
            packet = copy.deepcopy(client.game_state)
            packet["players"]["p"].update(x=int(edge), horizontal_progress=edge % 1)
            client.game_state = packet
            self.game._prediction = None
            self.game.render()
            target = self.game._display_camera
            self.assertGreater(target[0], start[0])
            self.assertEqual(draw.call_count, 2)
            for _ in range(30):
                self.game.render()
                self.assertEqual(self.game._display_camera, target)
            self.assertEqual(draw.call_count, 2)

    def test_pause_background_is_frozen_even_if_multiplayer_packets_change(self):
        snapshots = []

        def send(message):
            self.messages.append(message)
            packet = copy.deepcopy(client.game_state)
            if "pause" in message:
                packet["players"]["p"]["paused"] = message["pause"]
            if "input_seq" in message:
                packet["players"]["p"]["input_seq"] = message["input_seq"]
            client.game_state = packet

        def key_read(key):
            snapshots.append(self.screen.cells.copy())
            if key == -1:
                packet = copy.deepcopy(client.game_state)
                packet["enemies"] = {"e": {"x": 103, "y": 21}}
                client.game_state = packet

        self.game._send = send
        self.screen.keys.extend([-1, 27])
        self.screen.on_key = key_read
        with patch.object(self.game, "_compose_frame", wraps=self.game._compose_frame) as compose:
            self.assertTrue(self.game._pause())
            self.assertEqual(compose.call_count, 1)
        self.assertEqual(snapshots[0], snapshots[1])
        self.assertEqual(self.messages, [{"stop": True}, {"pause": True}, {"pause": False}])
        self.assertFalse(self.game._paused)

    def test_prediction_collision_uses_one_snapshot_throughout_a_frame(self):
        previous = client.game_state
        packet = copy.deepcopy(previous)
        packet["custom_tiles"] = {"101,21": {"char": "#"}}
        client.game_state = packet
        self.assertFalse(self.game._prediction_blocked(101, 21, previous))
        self.assertTrue(self.game._prediction_blocked(101, 21, packet))

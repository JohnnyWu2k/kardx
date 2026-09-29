import json
import random
import socket
import threading
import unittest
from unittest.mock import patch

from ttx.net import client, server
from ttx.world.map import InfiniteGameMap
from ttx.world.physics import grounded, jump, request_jump, step_actor, step_vertical, WALK_SPEED
from ttx.world.spawn import spawn_enemies, spawn_objects


class TerrainTests(unittest.TestCase):
    def test_generation_is_independent_of_chunk_size_and_order(self):
        a = InfiniteGameMap(180, seed=42)
        b = InfiniteGameMap(180, seed=42, chunk_width=11, chunk_height=7)
        coordinates = [(x, y) for x in range(1, 179, 7) for y in range(0, 100, 9)]
        expected = {(x, y): a.get_tile(x, y) for x, y in coordinates}
        self.assertEqual(expected, {(x, y): b.get_tile(x, y) for x, y in reversed(coordinates)})

    def test_seeds_change_terrain_and_hills_are_continuous(self):
        a, b = InfiniteGameMap(512, seed=1), InfiniteGameMap(512, seed=2)
        heights = [a.surface_height(x) for x in range(1, 511)]
        self.assertGreater(max(heights) - min(heights), 5)
        self.assertTrue(all(abs(a - b) <= 1 for a, b in zip(heights, heights[1:])))
        self.assertNotEqual(heights, [b.surface_height(x) for x in range(1, 511)])

    def test_underground_has_caves_and_clustered_ores(self):
        game_map = InfiniteGameMap(180, seed=42)
        tiles = {(x, y): game_map.get_tile(x, y) for x in range(1, 179) for y in range(45, 90)}
        self.assertTrue(any(tile == "." for tile in tiles.values()))
        self.assertTrue(any(tile == "#" for tile in tiles.values()))
        for ore in ("o", "*"):
            positions = {position for position, tile in tiles.items() if tile == ore}
            self.assertTrue(positions)
            self.assertTrue(any((x + 1, y) in positions or (x, y + 1) in positions for x, y in positions))

    def test_spawns_have_support_and_stay_out_of_terrain(self):
        game_map = InfiniteGameMap(180, seed=11)
        x, y = game_map.spawn_position()
        actors = [dict(x=x, y=y)] + list(spawn_enemies(180, 192, seed=11, game_map=game_map).values())
        actors += list(spawn_objects(180, 192, seed=11, game_map=game_map).values())
        for actor in actors:
            self.assertTrue(game_map.is_walkable(actor["x"], actor["y"]))
            self.assertFalse(game_map.is_walkable(actor["x"], actor["y"] + 1))


class PhysicsTests(unittest.TestCase):
    def test_jump_arc_lands_and_cannot_double_jump(self):
        actor = {"x": 3, "y": 9}
        blocked = lambda x, y: y >= 10 or y < 0
        self.assertTrue(jump(actor, blocked))
        self.assertFalse(jump(actor, blocked))
        heights = []
        for _ in range(40):
            step_vertical(actor, blocked)
            heights.append(actor["y"])
        self.assertLess(min(heights), 5)
        self.assertEqual(actor["y"], 9)
        self.assertTrue(grounded(actor, blocked))

    def test_high_speed_falling_does_not_tunnel_through_floor(self):
        actor = {"x": 3, "y": 3, "vy": 100}
        for _ in range(10):
            step_vertical(actor, lambda x, y: y >= 5)
        self.assertEqual(actor["y"], 4)

    def test_jump_stops_at_ceiling(self):
        actor = {"x": 3, "y": 9}
        blocked = lambda x, y: y >= 10 or y <= 7
        jump(actor, blocked)
        heights = []
        for _ in range(30):
            step_vertical(actor, blocked)
            heights.append(actor["y"])
        self.assertEqual(min(heights), 8)
        self.assertEqual(actor["y"], 9)

    def test_acceleration_braking_and_air_reversal(self):
        actor = {"x": 20, "y": 19}
        blocked = lambda x, y: y >= 20 or y < 0
        speeds = []
        for _ in range(8):
            step_actor(actor, blocked, 1)
            speeds.append(actor["vx"])
        self.assertLess(speeds[0], speeds[-1])
        self.assertLessEqual(max(speeds), WALK_SPEED)
        before_stop = actor["x"]
        for _ in range(8):
            step_actor(actor, blocked)
        self.assertEqual(actor["vx"], 0)
        self.assertLessEqual(actor["x"] - before_stop, 1)
        jump(actor, blocked)
        for _ in range(4):
            step_actor(actor, blocked, 1)
        airborne_x = actor["x"]
        for _ in range(8):
            step_actor(actor, blocked, -1)
        self.assertLess(actor["x"], airborne_x)
        self.assertLess(actor["y"], 19)

    def test_horizontal_sweep_stops_at_walls_and_other_actors(self):
        actor = {"x": 3, "y": 9, "vx": 100}
        blocked = lambda x, y: x >= 5 or y >= 10
        for _ in range(10):
            step_actor(actor, blocked, 1)
        self.assertEqual(actor["x"], 4)
        self.assertEqual(actor["vx"], 0)
        self.assertEqual(actor["horizontal_progress"], 0)

    def test_jump_buffer_fires_on_landing_and_expires_in_midair(self):
        blocked = lambda x, y: y >= 10
        actor = {"x": 3, "y": 6, "vy": 0.8}
        request_jump(actor, blocked)
        for _ in range(3):
            step_actor(actor, blocked)
        self.assertLess(actor["vy"], 0)
        actor = {"x": 3, "y": 1, "vy": 0.0}
        request_jump(actor, blocked)
        for _ in range(15):
            step_actor(actor, blocked)
        self.assertEqual(actor["y"], 9)
        self.assertEqual(actor["vy"], 0)

    def test_coyote_jump_is_brief_and_cannot_be_reused(self):
        blocked = lambda x, y: x <= 3 and y >= 10
        actor = {"x": 3, "y": 9}
        for _ in range(3):
            step_actor(actor, blocked, 1)
        self.assertFalse(grounded(actor, blocked))
        self.assertTrue(jump(actor, blocked))
        self.assertFalse(jump(actor, blocked))
        actor = {"x": 3, "y": 9}
        for _ in range(7):
            step_actor(actor, blocked, 1)
        self.assertFalse(jump(actor, blocked))


class SimulationTests(unittest.TestCase):
    def setUp(self):
        server.reset_game_state(80, 30, seed=123)
        server.enemies.clear()
        server.objects.clear()
        server.players["p"] = {"x": 5, "y": 21, "inventory": {}, "facing": 1}
        server.enemy_rng = random.Random(123)

    def tearDown(self):
        server.players.clear()
        server.enemies.clear()
        server.objects.clear()
        server.custom_tiles.clear()

    def enemy(self, x=10):
        enemy = {"x": x, "y": 21, "direction": -1, "home_x": x, "aggro_radius": 12}
        server.enemies["e"] = enemy
        return enemy

    def ticks(self, count=5):
        for _ in range(count):
            server.tick_world()

    def test_enemy_chases_without_player_sending_input(self):
        enemy = self.enemy()
        self.ticks(25)
        self.assertEqual(enemy["mode"], "chase")
        self.assertEqual(enemy["x"], 6)
        self.assertEqual(server.players["p"]["x"], 5)

    def test_enemy_patrols_without_nearby_players(self):
        server.players.clear()
        enemy = self.enemy()
        self.ticks()
        self.assertEqual(enemy["mode"], "patrol")
        self.assertNotEqual(enemy["x"], 10)

    def test_enemy_chooses_nearest_available_player(self):
        enemy = self.enemy()
        server.players["near"] = {"x": 13, "y": server.world_map.surface_height(13) - 1}
        self.ticks()
        self.assertEqual(enemy["x"], 11)

    def test_enemy_cannot_cross_a_wall(self):
        enemy = self.enemy()
        for y in range(22):
            server.custom_tiles[f"9,{y}"] = {"x": 9, "y": y, "char": "#"}
        self.ticks(50)
        self.assertGreaterEqual(enemy["x"], 10)
        self.assertFalse(server._terrain_blocked(enemy["x"], enemy["y"]))
        self.assertEqual(enemy["mode"], "patrol")

    def test_enemy_jumps_over_low_obstacles(self):
        enemy = self.enemy()
        server.custom_tiles["9,21"] = {"x": 9, "y": 21, "char": "#"}
        self.ticks(35)
        self.assertLess(enemy["x"], 9)
        self.assertFalse(server._terrain_blocked(enemy["x"], enemy["y"]))

    def test_chase_ends_when_player_moves_far_away(self):
        enemy = self.enemy()
        self.ticks()
        server.players["p"]["x"] = 100
        server.players["p"]["y"] = server.world_map.surface_height(100) - 1
        self.ticks()
        self.assertEqual(enemy["mode"], "patrol")

    def test_enemy_returns_toward_its_patrol_area_after_chasing(self):
        server.players.clear()
        enemy = self.enemy()
        enemy.update(x=30, y=server.world_map.surface_height(30) - 1)
        self.ticks()
        self.assertEqual(enemy["direction"], -1)

    def test_enemies_do_not_overlap(self):
        first = self.enemy(9)
        second = dict(first, x=10, home_x=10)
        server.enemies["second"] = second
        for _ in range(40):
            server.tick_world()
            self.assertNotEqual((first["x"], first["y"]), (second["x"], second["y"]))

    def test_player_falls_and_jumps_but_cannot_fly_or_teleport(self):
        player = server.players["p"]
        server.process_message("p", {"dx": 500, "dy": -100})
        self.assertEqual((player["x"], player["y"]), (5, 21))
        server.process_message("p", {"jump": True})
        self.ticks(3)
        self.assertLess(player["y"], 21)
        self.ticks(40)
        self.assertEqual(player["y"], 21)

    def test_mining_opens_ground_and_gravity_uses_the_override(self):
        server.process_message("p", {"gather": True, "dx": 0, "dy": 1})
        self.assertEqual(server.custom_tiles["5,22"]["char"], ".")
        self.assertEqual(server.players["p"]["inventory"]["dirt"], 1)
        self.ticks(10)
        self.assertEqual(server.players["p"]["y"], 22)

    def test_building_consumes_material_and_blocks_movement(self):
        player = server.players["p"]
        message = {"build": True, "x": 6, "y": 21, "material": "wood"}
        server.process_message("p", message)
        self.assertNotIn("6,21", server.custom_tiles)
        player["inventory"]["wood"] = 1
        server.process_message("p", message)
        self.assertEqual(player["inventory"]["wood"], 0)
        server.process_message("p", {"dx": 1})
        self.ticks(3)
        self.assertEqual(player["x"], 5)
        server.process_message("p", {"gather": True, "dx": 1})
        self.assertEqual(player["inventory"]["wood"], 1)
        server.process_message("p", {"dx": 1})
        self.ticks(3)
        self.assertEqual(player["x"], 6)

    def test_battle_reserves_enemy_and_release_restores_simulation(self):
        enemy = self.enemy(6)
        player = server.players["p"]
        server.process_message("p", {"battle": "start", "enemy_id": "e"})
        self.ticks(20)
        self.assertEqual(player["battle_enemy"], "e")
        self.assertEqual((enemy["x"], enemy["y"]), (6, 21))
        self.assertEqual(enemy["mode"], "battle")
        server.process_message("p", {"dx": -1})
        self.assertEqual(player["x"], 5)
        server.process_message("p", {"battle": "end"})
        self.assertNotIn("battle_enemy", player)
        self.assertNotIn("engaged_by", enemy)

    def test_remote_enemy_cannot_be_reserved_or_defeated(self):
        enemy = self.enemy(10)
        server.process_message("p", {"battle": "start", "enemy_id": "e"})
        server.process_message("p", {"attack": True, "enemy_id": "e", "defeated": True})
        self.assertNotIn("engaged_by", enemy)
        self.assertIn("e", server.enemies)

    def test_victory_releases_player_and_grants_rewards_once(self):
        self.enemy(6)
        server.process_message("p", {"battle": "start", "enemy_id": "e"})
        message = {"attack": True, "enemy_id": "e", "defeated": True}
        server.process_message("p", message)
        server.process_message("p", message)
        self.assertNotIn("e", server.enemies)
        self.assertNotIn("battle_enemy", server.players["p"])
        self.assertEqual(server.players["p"]["gold"], 5)

    def test_input_repeat_rate_does_not_change_speed(self):
        paths = []
        for messages_per_tick in (1, 20):
            server.players["p"] = {"x": 5, "y": 21}
            path = []
            for _ in range(12):
                for _ in range(messages_per_tick):
                    server.process_message("p", {"move": 1})
                server.tick_world()
                player = server.players["p"]
                path.append((player["x"], player["horizontal_progress"]))
            paths.append(path)
        self.assertEqual(paths[0], paths[1])

    def test_motion_times_out_and_simultaneous_jump_keeps_air_control(self):
        player = server.players["p"]
        server.process_message("p", {"move": 1, "jump": True})
        self.ticks(5)
        self.assertGreater(player["x"], 5)
        self.assertLess(player["y"], 21)
        self.ticks(20)
        self.assertEqual(player["move"], 0)
        self.assertEqual(player["vx"], 0)
        stopped_x = player["x"]
        self.ticks(20)
        self.assertEqual(player["x"], stopped_x)

    def test_enemy_does_not_acquire_a_player_through_a_wall(self):
        enemy = self.enemy()
        for y in range(22):
            server.custom_tiles[f"7,{y}"] = {"char": "#"}
        self.ticks(20)
        self.assertEqual(enemy["mode"], "patrol")
        self.assertNotIn("target_id", enemy)
        self.assertGreater(enemy["x"], 7)

    def test_occluded_enemy_searches_last_seen_position_then_forgets(self):
        enemy = self.enemy()
        self.ticks(2)
        self.assertEqual(enemy["mode"], "chase")
        self.assertEqual(enemy["last_seen_x"], 5)
        for y in range(22):
            server.custom_tiles[f"8,{y}"] = {"char": "#"}
        server.players["p"]["x"] = 6
        self.ticks(2)
        self.assertEqual(enemy["mode"], "search")
        self.assertEqual(enemy["last_seen_x"], 5)
        self.ticks(20)
        self.assertEqual(enemy["mode"], "patrol")
        self.assertNotIn("target_id", enemy)

    def test_sight_does_not_cut_solid_diagonal_corners(self):
        self.assertTrue(server._has_line_of_sight({"x": 5, "y": 10}, {"x": 7, "y": 12}))
        server.custom_tiles["6,10"] = {"char": "#"}
        self.assertFalse(server._has_line_of_sight({"x": 5, "y": 10}, {"x": 7, "y": 12}))

    def test_battle_clears_momentum_and_queued_jumps(self):
        enemy = self.enemy(6)
        player = server.players["p"]
        player.update(vx=0.4, vy=-1.0, jump_buffer=3, move=1)
        enemy.update(vx=-0.3, move=-1)
        server.process_message("p", {"battle": "start", "enemy_id": "e"})
        server.process_message("p", {"battle": "end"})
        self.assertEqual((player["move"], player["vx"], player["vy"], player["jump_buffer"]), (0, 0, 0, 0))
        self.assertEqual((enemy["move"], enemy["vx"]), (0, 0))
        self.ticks(1)
        self.assertEqual((player["x"], player["y"]), (5, 21))


class FakeScreen:
    def __init__(self, rows=30, columns=120):
        self.rows, self.columns = rows, columns
        self.cells = {}
        self.keys = []
        self.timeouts = []

    def getmaxyx(self):
        return self.rows, self.columns

    def addch(self, y, x, char, attr=0):
        if not (0 <= x < self.columns and 0 <= y < self.rows):
            raise client.curses.error("outside viewport")
        self.cells[y, x] = char

    def addstr(self, y, x, text, attr=0):
        for offset, char in enumerate(text):
            self.addch(y, x + offset, char)

    def clear(self):
        self.cells.clear()

    def refresh(self):
        pass

    def timeout(self, delay):
        self.timeouts.append(delay)

    def getch(self):
        return self.keys.pop(0) if self.keys else -1


class ClientTests(unittest.TestCase):
    def setUp(self):
        client.reset_client_state()
        self.game = object.__new__(client.Game)
        self.game.stdscr = FakeScreen()
        self.game.game_map = InfiniteGameMap(512, seed=42)
        self.game.scale = 1
        self.game.card_hp = None
        self.game.card_player_id = "player_balanced"
        self.game.card_deck_ids = self.game.card_max_hp = self.game.card_base_mana = None
        self.game._stop_event = None
        self.game.quit_to_menu = False
        self.game.building_mode_active = False
        self.game.build_direction = (1, 0)
        self.game.inventory = ["wood", "stone", "dirt", "sand", None]
        self.game.active_inventory_slot = 0
        self.game._dirty = False
        self.messages = []
        self.game._send = self.messages.append
        client.game_state.update(client_id="p", players={"p": {"x": 200, "y": 21}}, enemies={}, objects={})

    def tearDown(self):
        client.reset_client_state()

    def test_camera_follows_both_axes_and_clamps_at_world_edges(self):
        camera_x, camera_y = self.game._camera_offset()
        self.assertGreater(camera_x, 0)
        self.assertGreater(camera_y, 0)
        player = client.game_state["players"]["p"]
        player.update(x=511, y=191)
        game_width, _, _ = client.layout_columns(120)
        self.assertEqual(self.game._camera_offset(), (512 - game_width, 192 - 30))

    def test_controls_send_horizontal_jump_and_mining_messages(self):
        with patch.object(client.time, "monotonic", return_value=10.0):
            self.game.process_key(ord("d"))
            self.game.process_key(ord("w"))
            self.game._update_controls(10.0)
            self.game._update_controls(10.01)
            self.game.process_key(ord("s"))
        self.assertEqual(self.messages, [{"move": 1, "jump": True},
                                        {"gather": True, "dx": 0, "dy": 1}])
        self.game._update_controls(10.3)
        self.assertEqual(self.messages[-1], {"move": 0})

    def test_world_dimensions_come_from_server_instead_of_terminal(self):
        client.game_state.update(map_seed=42, world_width=512, world_height=192)
        terrain = []
        with patch.object(client.time, "sleep"):
            for columns in (80, 210):
                self.game.stdscr = FakeScreen(columns=columns)
                self.game.wait_for_map_seed()
                self.assertEqual(self.game.game_map.width, 512)
                terrain.append(self.game.game_map.get_tile(160, 40))
        self.assertEqual(terrain[0], terrain[1])

    def test_build_mode_aims_then_places_selected_material(self):
        self.game.process_key(ord("b"))
        self.game.process_key(ord("s"))
        self.game.process_key(ord("2"))
        self.game.process_key(10)
        self.assertEqual(self.messages, [{"move": 0}, {"build": True, "x": 200, "y": 22, "material": "stone"}])

    def test_mined_tiles_are_rendered_as_air_and_do_not_cover_player(self):
        player = client.game_state["players"]["p"]
        player.update(x=5, y=21, char="@")
        client.game_state["custom_tiles"] = {"5,22": {"x": 5, "y": 22, "char": "."}}
        with patch.object(client.curses, "color_pair", return_value=0):
            self.game.render()
        cx, cy = self.game._camera_offset()
        self.assertEqual(self.game.stdscr.cells[21 - cy, 5 - cx], "@")
        self.assertEqual(self.game.stdscr.cells[22 - cy, 5 - cx], " ")

    def test_render_handles_small_terminal_sizes(self):
        with patch.object(client.curses, "color_pair", return_value=0):
            for rows, columns in [(1, 1), (10, 20), (24, 80)]:
                self.game.stdscr = FakeScreen(rows, columns)
                self.game.render()
                self.assertTrue(all(0 <= y < rows and 0 <= x < columns for y, x in self.game.stdscr.cells))

    def test_camera_dead_zone_keeps_small_steps_and_jumps_from_scrolling(self):
        initial = self.game._camera_offset()
        client.game_state["players"]["p"].update(x=202, y=19)
        self.assertEqual(self.game._camera_offset(), initial)

    def test_terrain_cache_is_invalidated_by_mining(self):
        with patch.object(client.curses, "color_pair", return_value=0), patch.object(
            self.game.game_map, "draw_scaled", wraps=self.game.game_map.draw_scaled
        ) as draw:
            self.game.render()
            self.game.render()
            self.assertEqual(draw.call_count, 1)
            client.game_state["custom_tiles"] = {"200,22": {"char": "."}}
            self.game.render()
            self.assertEqual(draw.call_count, 2)

    def test_escape_pause_overlays_world_and_resume_restores_it(self):
        with patch.object(client.curses, "color_pair", return_value=0), patch.object(client.curses, "flushinp"):
            self.game.render()
            before = self.game.stdscr.cells.copy()
            self.game.stdscr.keys = [27]
            self.assertTrue(self.game._pause())
            self.assertEqual(self.messages[-1], {"move": 0})
            self.assertIn("Paused", "".join(self.game.stdscr.cells.values()))
            self.game.render()
            self.assertEqual(self.game.stdscr.cells, before)
            self.assertEqual(self.game.stdscr.timeouts[-1], 0)

    def test_card_pause_quit_returns_to_world_without_switching_terminal(self):
        player = client.game_state["players"]["p"]
        client.game_state["enemies"] = {"e": {"x": 201, "y": 21, "char": "E", "card_enemy_id": "enemy_giant_rat"}}

        def send(message):
            self.messages.append(message)
            if message.get("battle") == "start":
                player["battle_enemy"] = "e"
            elif message.get("battle") == "end":
                player.pop("battle_enemy", None)

        self.game._send = send
        self.game.stdscr.keys = [27, client.curses.KEY_DOWN, 10]
        with patch.object(client.curses, "color_pair", return_value=0), patch.object(client.curses, "flushinp"), patch(
            "ttx.terminal.time.sleep"
        ), patch.object(client.curses, "endwin", side_effect=AssertionError("terminal mode switch")):
            self.game._fight_adjacent_enemy()
        self.assertEqual(self.messages, [{"move": 0}, {"battle": "start", "enemy_id": "e"}, {"battle": "end"}])
        self.assertNotIn("battle_enemy", player)
        self.assertIsNotNone(self.game.card_hp)
        self.assertEqual(self.game.stdscr.timeouts[-1], 0)


class NetworkTests(unittest.TestCase):
    def test_idle_connection_receives_world_ticks_and_shutdown_is_clean(self):
        server.reset_game_state(80, 30, seed=123)
        server.server_stop_event.clear()
        local, peer = socket.socketpair()
        local.settimeout(2)
        handler = threading.Thread(target=server.handle_client, args=(peer, ("test", 1)))
        simulation = threading.Thread(target=server._simulation_loop)
        server.server_verbose = False
        handler.start()
        simulation.start()
        stream = local.makefile("r", encoding="utf-8")
        try:
            initial = json.loads(stream.readline())
            self.assertEqual(initial["world_width"], 512)
            self.assertEqual(initial["world_height"], 192)
            own_id = initial["client_id"]
            initial_positions = {key: (enemy["x"], enemy["y"]) for key, enemy in initial["enemies"].items()}
            for _ in range(30):
                state = json.loads(stream.readline())
                positions = {key: (enemy["x"], enemy["y"]) for key, enemy in state["enemies"].items()}
                if positions != initial_positions:
                    break
            self.assertNotEqual(positions, initial_positions)
            self.assertEqual(state["players"][own_id]["y"], 21)
            local.sendall(b'{"jump": true}\n')
            for _ in range(30):
                state = json.loads(stream.readline())
                if state["players"][own_id]["y"] < 21:
                    break
            self.assertLess(state["players"][own_id]["y"], 21)
        finally:
            server.server_stop_event.set()
            local.shutdown(socket.SHUT_RDWR)
            stream.close()
            local.close()
            handler.join(timeout=2)
            simulation.join(timeout=2)
        self.assertFalse(handler.is_alive())
        self.assertFalse(simulation.is_alive())
        self.assertFalse(server.connections)

import json
import unittest

from ttx.net import server
from ttx.net import client
from ttx.net.client import layout_columns
from ttx.world.map import InfiniteGameMap
from ttx.world.spawn import spawn_enemies, spawn_objects


class TTXTests(unittest.TestCase):
    def test_server_state_is_json_serializable(self):
        previous_tiles = dict(server.custom_tiles)
        try:
            server.custom_tiles.clear()
            server.custom_tiles["1,2"] = {"x": 1, "y": 2, "block": "#", "char": "#"}
            encoded = json.dumps(server.build_state("client-1"))
        finally:
            server.custom_tiles.clear()
            server.custom_tiles.update(previous_tiles)
        self.assertIn("client-1", encoded)
        self.assertIn("1,2", encoded)

    def test_new_server_game_clears_previous_state(self):
        server.players["old"] = {"x": 1, "y": 1}
        server.custom_tiles["1,1"] = {"x": 1, "y": 1, "char": "#"}
        server.enemies["old_enemy"] = {"x": 2, "y": 2, "char": "E"}

        server.reset_game_state(80, 30, seed=123)

        self.assertEqual(server.map_seed, 123)
        self.assertEqual(server.players, {})
        self.assertEqual(server.custom_tiles, {})
        self.assertNotIn("old_enemy", server.enemies)
        self.assertTrue(server.enemies)
        self.assertTrue(server.objects)

    def test_client_state_reset_clears_previous_world_cache(self):
        client.game_state["map_seed"] = 99
        client.game_state["players"] = {"old": {"x": 1, "y": 1}}

        client.reset_client_state()

        self.assertEqual(client.game_state, {})

    def test_world_spawns_card_enemies_and_resources(self):
        enemies = spawn_enemies(60, 30, seed=1)
        self.assertTrue(enemies)
        self.assertTrue(all(enemy.get("card_enemy_id") for enemy in enemies.values()))

        game_map = InfiniteGameMap(60, seed=1)
        objects = spawn_objects(60, 30, seed=2, game_map=game_map)
        self.assertIsInstance(objects, dict)
        self.assertTrue(all("drop" in obj for obj in objects.values()))

    def test_world_map_has_sky_surface_and_underground_layers(self):
        game_map = InfiniteGameMap(120, seed=3)
        for x in range(1, 119):
            surface = game_map.surface_height(x)
            self.assertEqual(game_map.get_tile(x, surface - 1), ".")
            self.assertIn(game_map.get_tile(x, surface), {'"', "%"})
            self.assertIn(game_map.get_tile(x, surface + 2), {":", "%"})
            self.assertIn(game_map.get_tile(x, surface + 5), {"#", "o", "c"})
        self.assertEqual(game_map.get_tile(5, 5), ".")

    def test_resource_spawns_are_sparse_and_clustered(self):
        width, height = 120, 40
        game_map = InfiniteGameMap(width, seed=3)
        objects = spawn_objects(width, height, seed=3, game_map=game_map)
        self.assertGreater(len(objects), 0)
        self.assertLess(len(objects), width * height * 0.02)

        values = list(objects.values())
        nearby_pairs = sum(
            1
            for index, obj in enumerate(values)
            for other in values[index + 1 :]
            if abs(obj["x"] - other["x"]) + abs(obj["y"] - other["y"]) <= 3
        )
        self.assertGreater(nearby_pairs, 0)

    def test_layout_columns_stay_inside_terminal_width(self):
        for max_x in [1, 2, 10, 40, 80, 120]:
            game_width, panel_x, panel_width = layout_columns(max_x)
            self.assertGreaterEqual(game_width, 0)
            self.assertGreaterEqual(panel_width, 0)
            self.assertLessEqual(panel_x + panel_width, max_x)

    def test_layout_columns_keep_stable_ratio_for_supported_sizes(self):
        for max_x in [120, 150, 180, 210]:
            _, _, panel_width = layout_columns(max_x)
            self.assertAlmostEqual(panel_width / max_x, 0.25, delta=0.02)


if __name__ == "__main__":
    unittest.main()

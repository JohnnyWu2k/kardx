import random
import tempfile
import unittest
from pathlib import Path

from kardx.sandbox import BattleSession, SandboxData, SandboxGame


class SandboxTests(unittest.TestCase):
    def make_game(self) -> SandboxGame:
        game = SandboxGame(rng=random.Random(1))
        game.start("player_balanced")
        return game

    def test_data_references_are_valid(self):
        errors = SandboxData().validate()
        self.assertEqual(errors, [])

    def test_locked_exit_requires_key_use(self):
        game = self.make_game()
        game.go("east")
        game.take("key")
        game.go("west")
        game.go("north")

        blocked = game.go("north")
        self.assertIn("locked", blocked[0])
        self.assertEqual(game.state.current_room, "hall")

        game.use("key")
        moved = game.go("north")
        self.assertIn("Outside", "\n".join(moved))
        self.assertEqual(game.state.current_room, "outside")

    def test_forage_adds_item_and_sets_cooldown(self):
        game = self.make_game()
        game.go("east")

        first = game.forage()
        self.assertIn("find", first[0])
        self.assertTrue(game.state.inventory)

        second = game.forage()
        self.assertEqual(second, ["This area has been picked clean for now."])

    def test_craft_can_add_and_upgrade_cards(self):
        game = self.make_game()
        game.state.add_item("crystal_shard", 1)
        game.state.add_item("scrap", 1)
        game.state.add_item("wood", 1)
        game.state.add_item("stone", 1)

        add_messages = game.craft("mana_gem")
        self.assertIn("mana_gem", game.state.deck_ids)
        self.assertIn("Added card", "\n".join(add_messages))

        strike_count = game.state.deck_ids.count("strike")
        upgrade_messages = game.craft("double_strike")
        self.assertEqual(game.state.deck_ids.count("strike"), strike_count - 1)
        self.assertIn("double_strike", game.state.deck_ids)
        self.assertIn("became", "\n".join(upgrade_messages))

    def test_save_and_load_roundtrip(self):
        game = self.make_game()
        game.state.current_room = "outside"
        game.state.add_item("wood", 2)
        game.state.flags.add("test_flag")
        game.state.quests["Explore"] = "active"
        game.state.room_items["storage"] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            save_dir = Path(temp_dir)
            game.save("slot1", save_dir=save_dir)

            loaded_game = SandboxGame()
            loaded = loaded_game.load("slot1", save_dir=save_dir)

        self.assertEqual(loaded.current_room, "outside")
        self.assertEqual(loaded.inventory["wood"], 2)
        self.assertIn("test_flag", loaded.flags)
        self.assertEqual(loaded.quests["Explore"], "active")
        self.assertEqual(loaded.room_items["storage"], [])

    def test_battle_session_syncs_victory_to_run_state(self):
        game = self.make_game()
        game.state.current_room = "dungeon_room1"
        session = BattleSession(game, "rat_passage")
        session.game.player.hp = 7
        session.game.player.max_mana = 4

        messages = session.finish("victory")

        self.assertEqual(game.state.current_hp, 7)
        self.assertEqual(game.state.base_mana, 4)
        self.assertIn("rat_passage", game.state.defeated_encounters)
        self.assertIn("rat_defeated", game.state.flags)
        self.assertEqual(game.state.quests["Explore the Old Well"], "complete")
        self.assertGreaterEqual(game.state.gold, 10)
        self.assertIn("Victory", messages[0])


if __name__ == "__main__":
    unittest.main()

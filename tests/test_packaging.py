"""Check that installed distributions expose commands and ship game data."""

import unittest
from importlib.metadata import distribution
from importlib.resources import files


class PackagingTests(unittest.TestCase):
    def test_console_scripts_can_be_loaded(self):
        scripts = {
            entry.name: entry
            for entry in distribution("ttx").entry_points
            if entry.group == "console_scripts"
        }
        self.assertEqual(set(scripts), {"ttx", "kardx", "sandkard"})
        for name, entry in scripts.items():
            with self.subTest(command=name):
                self.assertTrue(callable(entry.load()))

    def test_all_game_data_is_packaged(self):
        data = files("kardx.data")
        for name in (
            "adventures", "cards", "characters", "encounters", "events",
            "recipes", "relics", "settings", "world",
        ):
            with self.subTest(data=name):
                resource = data.joinpath(f"{name}.jsonc")
                self.assertTrue(resource.is_file())
                self.assertTrue(resource.read_text(encoding="utf-8").strip())

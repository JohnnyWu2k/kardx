"""Check that installed distributions expose commands and ship game data."""

import curses
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib.metadata import distribution
from importlib.resources import files
from io import StringIO
from unittest.mock import patch

from ttx import __version__
from ttx.cli import main


class PackagingTests(unittest.TestCase):
    def test_console_scripts_can_be_loaded(self):
        scripts = {
            entry.name: entry
            for entry in distribution("kard-x-sandbox").entry_points
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

    def test_pixel_art_assets_are_packaged(self):
        assets = files("ttx").joinpath("assets")
        for name in ("woodland_tree.png", "grass_road.png"):
            with self.subTest(asset=name):
                resource = assets.joinpath(name)
                self.assertTrue(resource.is_file())
                self.assertGreater(len(resource.read_bytes()), 0)

    def test_runtime_version_uses_distribution_metadata(self):
        package = distribution("kard-x-sandbox")
        self.assertEqual(package.metadata["Name"], "kard-x-sandbox")
        self.assertEqual(__version__, package.version)
        self.assertEqual(package.metadata["License-Expression"], "MIT")

    def test_help_and_version_do_not_initialize_the_terminal(self):
        for option in ("--help", "--version"):
            with self.subTest(option=option), patch("ttx.cli.maximize_terminal") as maximize, patch(
                "ttx.cli.curses.wrapper"
            ) as wrapper, redirect_stdout(StringIO()) as output:
                with self.assertRaises(SystemExit) as result:
                    main([option])
                self.assertEqual(result.exception.code, 0)
                self.assertIn("kard-x-sandbox" if option == "--version" else "Kard-X Sandbox", output.getvalue())
                maximize.assert_not_called()
                wrapper.assert_not_called()

    def test_interrupt_and_terminal_error_have_clean_exit_codes(self):
        for error, expected in ((KeyboardInterrupt(), 130), (curses.error("no terminal"), 1)):
            with self.subTest(error=type(error).__name__), patch("ttx.cli.maximize_terminal"), patch(
                "ttx.cli.curses.wrapper", side_effect=error
            ), redirect_stderr(StringIO()) as output:
                self.assertEqual(main([]), expected)
                if expected == 1:
                    self.assertIn("no terminal", output.getvalue())

"""Render the actual hotbar and backpack frames for layout review."""
import curses
from pathlib import Path
from unittest.mock import patch

from preview_world import make_game, frame_image
from ttx.inventory_ui import backpack_frame
from ttx.world.inventory import sync_slots


def main():
    game, state = make_game()
    game.stdscr.getmaxyx = lambda: (38, 144)
    inventory = {"wood": 8, "stone": 22, "dirt": 14, "workbench": 1, "wood_pickaxe": 1,
                 "stone_pickaxe": 1, "iron_ore": 18, "lead_ore": 6, "coal": 12, "stick": 2,
                 "sand": 9, "crystal_shard": 3}
    state["players"]["p"]["inventory"] = inventory
    game.inventory = sync_slots([], inventory)
    output = Path("dist")
    output.mkdir(exist_ok=True)
    with patch.object(curses, "color_pair", new=lambda i: i << 8), patch.object(
        curses, "A_COLOR", 0xff00
    ), patch("ttx.world.materials._extended_pairs", True), patch("ttx.net.client.game_state", state):
        frame = game._compose_frame()
        frame_image(frame).save(output / "inventory-hotbar.png")
        overlay, _ = backpack_frame(frame, game.inventory, inventory, 5, 0)
        frame_image(overlay).save(output / "inventory-backpack.png")
        state["players"]["p"]["inventory"] = {}
        frame_image(game._compose_frame()).save(output / "inventory-empty.png")


if __name__ == "__main__":
    main()

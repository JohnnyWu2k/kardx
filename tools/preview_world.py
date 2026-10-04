"""Render an offline world frame with the same camera, tiles and HUD as TTX."""
import curses
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont
from ttx.net.client import Game
from ttx.world.map import InfiniteGameMap
from ttx.world.materials import PALETTE, PAIR_START, QUADRANTS


class Screen:
    def getmaxyx(self):
        return 38, 144


def make_game():
    game = Game.__new__(Game)
    game.stdscr = Screen()
    game.game_map = InfiniteGameMap(512, seed=42)
    game.scale, game.smooth_graphics = 1, True
    game.building_mode_active = False
    game.inventory = ["wood", "stone", "dirt", "workbench", "wood_pickaxe"]
    game.active_inventory_slot, game.card_hp = 0, None
    game.mouse_raw_x = game.mouse_raw_y = None
    tiles = {}
    for y in range(24, 32):
        for x in range(4, 26):
            char = ("#", "o", "c", "l", "*")[(x // 3) % 5] if y % 3 == 0 else "#"
            tiles[f"{x},{y}"] = {"x": x, "y": y, "char": char}
    state = {"client_id": "p", "players": {"p": {"x": 13, "y": 21, "inventory": {"wood": 8, "wood_pickaxe": 1}}},
             "enemies": {}, "objects": {"tree": {"x": 17, "y": 21, "type": "tree"}}, "custom_tiles": tiles}
    state["players"]["p"]["y"] = game.game_map.surface_height(13) - 1
    state["objects"]["tree"]["y"] = game.game_map.surface_height(17) - 1
    game._view_state = lambda _: state
    return game, state


def frame_image(frame, cw=10, ch=20):
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", ch - 4)
    except OSError:
        font = ImageFont.load_default()
    image = Image.new("RGB", (frame.columns * cw, frame.rows * ch), PALETTE[0])
    draw = ImageDraw.Draw(image)
    palette = {2: "#4eaf46", 3: "#9fadb9", 4: "#60c6db", 5: "#e66554", 6: "#9b713f", 7: "#d2aa65", 8: "#7e91bb", 10: "#454852"}
    masks = {char: mask for mask, char in enumerate(QUADRANTS)}
    for y, row in enumerate(frame.cells):
        for x, (char, attr) in enumerate(row):
            pair = (attr >> 8) & 255
            if PAIR_START <= pair < PAIR_START + len(PALETTE) ** 2:
                fg, bg = divmod(pair - PAIR_START, len(PALETTE))
                color = PALETTE[fg]
                draw.rectangle((x * cw, y * ch, (x + 1) * cw - 1, (y + 1) * ch - 1), fill=PALETTE[bg])
            else:
                color = palette.get(pair, "#ccd0d5")
            if attr & curses.A_REVERSE:
                draw.rectangle((x * cw, y * ch, (x + 1) * cw - 1, (y + 1) * ch - 1), fill="#ccd0d5")
                color = PALETTE[0]
            if char in masks:
                mask = masks[char]
                for py in range(2):
                    for px in range(2):
                        if mask & (1 << (py * 2 + px)):
                            draw.rectangle((x * cw + px * cw // 2, y * ch + py * ch // 2,
                                            x * cw + (px + 1) * cw // 2 - 1, y * ch + (py + 1) * ch // 2 - 1), fill=color)
            elif char:
                draw.text((x * cw, y * ch), char, font=font, fill=color)
    return image


def main():
    game, state = make_game()
    with patch.object(curses, "color_pair", side_effect=lambda i: i << 8), patch.object(
        curses, "A_COLOR", 0xff00
    ), patch("ttx.world.materials._extended_pairs", True):
        frame = game._compose_frame()
    Path("dist").mkdir(exist_ok=True)
    frame_image(frame).save("dist/world-progression.png")


if __name__ == "__main__":
    main()

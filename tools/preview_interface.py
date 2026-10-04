"""Render the real battle layout to PNG without opening a terminal window."""
import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from kardx.scenes.game.game_view import GameView
from kardx.view_utils import use_terminal
from ttx.combat.card_battle import prepare_card_battle
from ttx.art import PALETTE


class Preview:
    def __init__(self, columns, rows):
        self.columns, self.rows = columns, rows
        self.lines = []
    def size(self):
        return self.columns, self.rows
    def render(self, lines):
        self.lines = lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--columns", type=int, default=120)
    parser.add_argument("--rows", type=int, default=30)
    parser.add_argument("--output", default="dist/battle-preview.png")
    args = parser.parse_args()
    terminal = Preview(args.columns, args.rows)
    game = prepare_card_battle("enemy_giant_rat", deck_ids=["strike", "defend", "first_aid", "mana_gem", "double_strike"])
    game.start_battle()
    game.start_player_turn()
    with use_terminal(terminal):
        GameView().display_board(game.player, game.enemy, game.action_log, selected_index=0)
    font_path = next((path for path in (Path("C:/Windows/Fonts/consola.ttf"),
                      Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")) if path.exists()), None)
    font = ImageFont.truetype(str(font_path), 18) if font_path else ImageFont.load_default()
    cell_width, cell_height = round(font.getlength("M")), 24
    image = Image.new("RGB", (args.columns * cell_width + 32, args.rows * cell_height + 32), "#10151c")
    draw = ImageDraw.Draw(image)
    colors = {"91": "#ff7979", "92": "#8be9ad", "94": "#83baff", "96": "#7adce8", "97": "#eff3fa"}
    for row, line in enumerate(terminal.lines):
        x, color, background = 16, "#c8d1de", "#10151c"
        for part in re.split(r"(\033\[[0-9;]*m)", line):
            if part.startswith("\033"):
                for value in part[2:-1].split(";"):
                    code = int(value or 0)
                    if code == 0:
                        color, background = "#c8d1de", "#10151c"
                    elif 30 <= code <= 37:
                        color = PALETTE[code - 30]
                    elif 40 <= code <= 47:
                        background = PALETTE[code - 40]
                    elif value in colors:
                        color = colors[value]
            else:
                for char in part:
                    top = row * cell_height + 16
                    draw.rectangle((x, top, x + cell_width - 1, top + cell_height - 1), fill=background)
                    if char == "▀":
                        draw.rectangle((x, top, x + cell_width - 1, top + cell_height // 2 - 1), fill=color)
                    else:
                        draw.text((x, top), char, font=font, fill=color)
                    x += cell_width
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


if __name__ == "__main__":
    main()

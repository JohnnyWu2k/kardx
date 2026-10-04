"""Packaged pixel atlas, sampled on a fixed grid without interpolation."""
from functools import lru_cache
from importlib.resources import files

from PIL import Image

REGIONS = {"attack": (0, 0), "defend": (1, 0), "heal": (2, 0), "mana": (3, 0),
           "fire": (0, 1), "ice": (1, 1), "dirt": (2, 1), "stone": (3, 1)}
PALETTE = ((8, 14, 25), (210, 55, 40), (65, 185, 65), (220, 174, 65),
           (65, 100, 205), (170, 65, 205), (55, 195, 215), (220, 229, 235))


@lru_cache(maxsize=8)
def atlas_region(name):
    with files("ttx").joinpath("assets", "fantasy_atlas.png").open("rb") as stream:
        with Image.open(stream) as image:
            column, row = REGIONS[name]
            return image.crop((column * image.width // 4, row * image.height // 2,
                               (column + 1) * image.width // 4, (row + 1) * image.height // 2)).convert("RGB")


@lru_cache(maxsize=128)
def card_pixels(name, width, rows):
    image = atlas_region(name).resize((width, rows * 2), Image.Resampling.NEAREST)
    def color(pixel):
        return min(range(8), key=lambda i: sum((a - b) ** 2 for a, b in zip(pixel, PALETTE[i])))
    result = []
    for y in range(rows):
        line = []
        for x in range(width):
            foreground = color(image.getpixel((x, y * 2)))
            background = color(image.getpixel((x, y * 2 + 1)))
            line.append(f"\033[3{foreground};4{background}m▀")
        result.append("".join(line) + "\033[0m")
    return tuple(result)

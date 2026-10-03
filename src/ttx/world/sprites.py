"""Load compressed PNG art once and project it onto the terminal dot canvas."""

from __future__ import annotations

import curses
from functools import lru_cache
from importlib import resources

from PIL import Image


def _shade(red: int, green: int, blue: int) -> int:
    if green > red * 1.05:
        return curses.color_pair(2) | (curses.A_BOLD if green >= 150 else 0)
    if red >= 200 and green >= 160:
        return curses.color_pair(3) | curses.A_BOLD
    if red < 95:
        return curses.color_pair(6) | curses.A_DIM
    return curses.color_pair(6) | (curses.A_BOLD if red >= 175 else 0)


class PixelSprite:
    def __init__(self, image: Image.Image, width: int, height: int, textured: bool = False):
        source = image.convert("RGBA")
        sample = source.resize((width, height), Image.Resampling.BOX)
        self.width, self.height = width, height
        self.pixels = []
        flat = iter(sample.get_flattened_data())
        for y in range(height):
            row = []
            for x in range(width):
                red, green, blue, alpha = next(flat)
                visible = alpha >= 112
                if textured:
                    # Bright stones and dark cracks disappear under ordinary
                    # averaging at only four dots per world tile. Preserve
                    # those large source features as deliberate pixel marks.
                    box = source.crop((x * source.width // width, y * source.height // height,
                                       (x + 1) * source.width // width,
                                       (y + 1) * source.height // height))
                    points = tuple(box.get_flattened_data())
                    stones = [pixel for pixel in points if pixel[0] >= 210 and pixel[1] >= 170]
                    if stones:
                        red, green, blue, _ = max(stones, key=lambda pixel: sum(pixel[:3]))
                    elif sum(pixel[0] < 120 and pixel[1] < 90 for pixel in points) >= len(points) * 0.35:
                        visible = False
                row.append((visible, _shade(red, green, blue) if visible else 0))
            self.pixels.append(tuple(row))
        self.pixels = tuple(self.pixels)

    def blit(self, canvas, left: int, top: int, priority: int = 1,
             source_x: int = 0, width: int | None = None):
        width = self.width - source_x if width is None else width
        for y, row in enumerate(self.pixels):
            for x in range(width):
                visible, attr = row[source_x + x]
                if visible:
                    canvas.dot(left + x, top + y, attr, priority=priority)


@lru_cache(maxsize=2)
def load_sprite(name: str) -> PixelSprite:
    if name == "tree":
        filename, width, height, textured = "woodland_tree.png", 12, 24, False
    elif name == "road":
        filename, width, height, textured = "grass_road.png", 8, 4, True
    else:
        raise ValueError(f"Unknown sprite: {name}")
    with resources.files("ttx").joinpath("assets", filename).open("rb") as stream:
        with Image.open(stream) as image:
            return PixelSprite(image, width, height, textured)

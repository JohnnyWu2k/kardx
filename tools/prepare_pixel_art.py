"""Turn generated source art into small, sharp, game-ready PNG sprites.

Usage: uv run python tools/prepare_pixel_art.py TREE_SOURCE ROAD_SOURCE
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parents[1] / "src" / "ttx" / "assets"
TREE_PALETTE = ((7, 50, 23), (37, 111, 46), (101, 160, 63),
                (164, 201, 77), (57, 34, 21), (131, 76, 42), (183, 116, 70))
ROAD_PALETTE = ((61, 36, 24), (105, 66, 41), (155, 102, 59),
                (188, 128, 75), (224, 192, 150), (72, 109, 43), (153, 178, 61))


def _closest(rgb, palette):
    return min(palette, key=lambda color: sum((a - b) ** 2 for a, b in zip(rgb, color)))


def _quantize(image: Image.Image, palette, transparent: bool) -> Image.Image:
    pixels = []
    for red, green, blue, alpha in image.convert("RGBA").get_flattened_data():
        if transparent and alpha < 112:
            pixels.append((0, 0, 0, 0))
        else:
            pixels.append((*_closest((red, green, blue), palette), 255))
    output = Image.new("RGBA", image.size)
    output.putdata(pixels)
    return output


def prepare_tree(source: Path, destination: Path):
    with Image.open(source) as original:
        image = original.convert("RGBA")
        alpha = image.getchannel("A").point(lambda value: 255 if value >= 112 else 0)
        bounds = alpha.getbbox()
        if not bounds:
            raise ValueError("The tree source has no visible pixels")
        image = image.crop(bounds).resize((48, 72), Image.Resampling.BOX)
        image = _quantize(image, TREE_PALETTE, transparent=True)
        image.save(destination, optimize=True)


def prepare_road(source: Path, destination: Path):
    with Image.open(source) as original:
        image = original.convert("RGB")
        middle = image.width // 2
        colored = [y for y in range(image.height)
                   if min(image.getpixel((middle, y))) < 225]
        if not colored:
            raise ValueError("The road source contains no colored strip")
        repeat_pair_width = image.width // 2
        image = image.crop((0, colored[0], repeat_pair_width, colored[-1] + 1))
        image = image.resize((32, 16), Image.Resampling.BOX)
        image = _quantize(image, ROAD_PALETTE, transparent=False)
        image.save(destination, optimize=True)


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    ASSETS.mkdir(parents=True, exist_ok=True)
    prepare_tree(Path(sys.argv[1]), ASSETS / "woodland_tree.png")
    prepare_road(Path(sys.argv[2]), ASSETS / "grass_road.png")
    for filename in ("woodland_tree.png", "grass_road.png"):
        with Image.open(ASSETS / filename) as sprite:
            print(filename, sprite.size, (ASSETS / filename).stat().st_size, "bytes")


if __name__ == "__main__":
    main()

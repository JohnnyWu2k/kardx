"""Compile the generated atlas to the tiny palette-mapped runtime PNG.

Run with `uv run python tools/prepare_terrain.py`. Nearest-neighbor sampling
keeps the authored pixels crisp; there is no filtering, blur or added shading.
"""
from pathlib import Path

from PIL import Image
from ttx.world.materials import MATERIALS, PALETTE, nearest_color


def main():
    assets = Path(__file__).resolve().parents[1] / "src" / "ttx" / "assets"
    result = Image.new("RGB", (64, 32))
    with Image.open(assets / "terrain_atlas.png") as atlas:
        for index, _ in enumerate(MATERIALS):
            x, y = index % 4, index // 4
            tile = atlas.crop((x * atlas.width // 4, y * atlas.height // 2,
                               (x + 1) * atlas.width // 4, (y + 1) * atlas.height // 2))
            tile = tile.convert("RGB").resize((16, 16), Image.Resampling.NEAREST)
            tile.putdata([PALETTE[nearest_color(rgb)] for rgb in tile.get_flattened_data()])
            result.paste(tile, (x * 16, y * 16))
    result.save(assets / "terrain_tiles.png", optimize=True)


if __name__ == "__main__":
    main()

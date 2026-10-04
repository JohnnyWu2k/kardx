"""Small packaged terrain textures and opaque terminal quadrant colors."""
import curses
from functools import lru_cache
from importlib.resources import files

from PIL import Image

MATERIALS = ("dirt", "stone", "iron", "coal", "lead", "crystal", "sand", "wood")
TILE_MATERIALS = {":": "dirt", '"': "dirt", "#": "stone", "o": "iron",
                  "c": "coal", "l": "lead", "*": "crystal", "%": "sand", "|": "wood"}
# 13 squared pairs fit alongside the existing UI/card pairs in a 256-pair terminal.
PALETTE = ((12, 15, 19), (58, 61, 65), (105, 107, 108), (163, 167, 169),
           (83, 48, 27), (139, 82, 43), (200, 116, 65), (243, 172, 114),
           (198, 158, 80), (81, 143, 64), (111, 151, 186), (53, 204, 224),
           (237, 211, 153))
PAIR_START = 80
FALLBACK = (0, 0, 7, 7, 3, 3, 3, 3, 3, 2, 4, 6, 7)
QUADRANTS = (" ", "▘", "▝", "▀", "▖", "▌", "▞", "▛", "▗", "▚", "▐", "▜", "▄", "▙", "▟", "█")
_extended_pairs = False


def nearest_color(rgb):
    return min(range(len(PALETTE)), key=lambda i: sum((a - b) ** 2 for a, b in zip(rgb, PALETTE[i])))


def init_material_colors():
    global _extended_pairs
    _extended_pairs = False
    if getattr(curses, "COLOR_PAIRS", 0) < PAIR_START + len(PALETTE) ** 2:
        return
    colors = FALLBACK
    if getattr(curses, "COLORS", 0) >= 256:
        # Use standard xterm entries without changing the user's terminal palette.
        levels = (0, 95, 135, 175, 215, 255)
        xterm = [(16 + r * 36 + g * 6 + b, (red, green, blue))
                 for r, red in enumerate(levels) for g, green in enumerate(levels)
                 for b, blue in enumerate(levels)]
        xterm += [(232 + i, (8 + i * 10,) * 3) for i in range(24)]
        colors = tuple(min(xterm, key=lambda entry: sum((a - b) ** 2 for a, b in zip(rgb, entry[1])))[0]
                       for rgb in PALETTE)
    try:
        for foreground, fg in enumerate(colors):
            for background, bg in enumerate(colors):
                curses.init_pair(PAIR_START + foreground * len(PALETTE) + background, fg, bg)
    except curses.error:
        return
    _extended_pairs = True


def material_attr(foreground, background):
    if _extended_pairs:
        return curses.color_pair(PAIR_START + foreground * len(PALETTE) + background)
    return curses.color_pair(16 + FALLBACK[foreground] * 8 + FALLBACK[background])


def material_attributes():
    """Resolve curses attributes once per frame instead of once per pixel cell."""
    return tuple(tuple(material_attr(fg, bg) for bg in range(len(PALETTE))) for fg in range(len(PALETTE)))


@lru_cache(maxsize=8)
def material_pixels(name):
    index = MATERIALS.index(name)
    with files("ttx").joinpath("assets", "terrain_tiles.png").open("rb") as stream:
        with Image.open(stream) as atlas:
            image = atlas.crop((index % 4 * 16, index // 4 * 16,
                                index % 4 * 16 + 16, index // 4 * 16 + 16)).convert("RGB")
    return tuple(tuple(nearest_color(image.getpixel((x, y))) for x in range(16)) for y in range(16))


@lru_cache(maxsize=512)
def tile_stamp(tile, variant_x, variant_y, offset_x, offset_y):
    """Pre-split a world tile into terminal cells, including fractional edges."""
    texture = material_pixels(TILE_MATERIALS.get(tile, "stone"))
    cells = {}
    for y in range(8):
        for x in range(8):
            sx, sy = x + offset_x, y + offset_y
            cell = cells.setdefault((sx // 2, sy // 4), [-1] * 8)
            color = 9 if tile == '"' and y < 2 else texture[variant_y * 8 + y][variant_x * 8 + x]
            cell[sy % 4 * 2 + sx % 2] = color
    return tuple((x, y, tuple(colors), -1 not in colors) for (x, y), colors in cells.items())


@lru_cache(maxsize=16384)
def pixel_cell(colors):
    quads = tuple(max(0, colors[i] if colors[i] >= 0 else colors[i + 2]) for i in (0, 1, 4, 5))
    return quadrant_cell(quads)


@lru_cache(maxsize=8192)
def merge_cell(incoming, previous):
    return tuple(a if a >= 0 else b for a, b in zip(incoming, previous))


@lru_cache(maxsize=8192)
def quadrant_cell(pixels):
    """Quantize four opaque quadrants to the two colors a terminal cell holds."""
    counts = {color: pixels.count(color) for color in pixels}
    background = max(counts, key=counts.get)
    # Keep a mineral accent even when it occupies only one quadrant.
    foreground = max(counts, key=lambda c: sum((a - b) ** 2 for a, b in zip(PALETTE[c], PALETTE[background])))
    if foreground == background:
        return " ", background, background
    mask = 0
    for index, color in enumerate(pixels):
        distances = [sum((a - b) ** 2 for a, b in zip(PALETTE[color], PALETTE[c]))
                     for c in (background, foreground)]
        if distances[1] < distances[0]:
            mask |= 1 << index
    return QUADRANTS[mask], foreground, background

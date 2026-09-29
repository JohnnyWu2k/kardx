"""A 2x4 dot canvas gives terminal graphics movement within a character cell."""

import math

from ttx.world.physics import position

DOT_BITS = ((1, 8), (2, 16), (4, 32), (64, 128))
BLOCKS = {0: " ", 255: "█", 71: "▌", 184: "▐", 27: "▀", 228: "▄"}
GLYPHS = tuple(BLOCKS.get(mask, chr(0x2800 + mask)) for mask in range(256))
TILE_PIXELS = 4


class DotCanvas:
    def __init__(self, rows: int, columns: int):
        self.rows, self.columns = rows, columns
        self.cells = [[(0, 0, -1) for _ in range(columns)] for _ in range(rows)]

    def copy(self):
        result = object.__new__(DotCanvas)
        result.rows, result.columns = self.rows, self.columns
        result.cells = [row.copy() for row in self.cells]
        return result

    def dot(self, x: int, y: int, attr: int = 0, priority: int = 0):
        if not (0 <= x < self.columns * 2 and 0 <= y < self.rows * 4):
            return
        row, col = y // 4, x // 2
        mask, old_attr, old_priority = self.cells[row][col]
        bit = DOT_BITS[y % 4][x % 2]
        if priority >= old_priority:
            old_attr, old_priority = attr, priority
        self.cells[row][col] = mask | bit, old_attr, old_priority

    def rectangle(self, x: int, y: int, width: int, height: int, attr: int = 0):
        left, right = max(0, x), min(self.columns * 2, x + width)
        top, bottom = max(0, y), min(self.rows * 4, y + height)
        if left >= right or top >= bottom:
            return
        for row in range(top // 4, (bottom + 3) // 4):
            start, end = max(0, top - row * 4), min(4, bottom - row * 4)
            left_mask = sum(DOT_BITS[py][0] for py in range(start, end))
            right_mask = sum(DOT_BITS[py][1] for py in range(start, end))
            for col in range(left // 2, (right + 1) // 2):
                bits = (left_mask if col * 2 >= left else 0) | (right_mask if col * 2 + 1 < right else 0)
                mask, old_attr, priority = self.cells[row][col]
                self.cells[row][col] = mask | bits, attr if priority <= 0 else old_attr, max(0, priority)

    def paint(self, frame):
        for y, row in enumerate(self.cells):
            for x, (mask, attr, _) in enumerate(row):
                frame.addch(y, x, GLYPHS[mask], attr)


def origin(camera: tuple[float, float]) -> tuple[int, int]:
    return round(camera[0] * TILE_PIXELS), round(camera[1] * TILE_PIXELS)


def project(actor: dict, camera: tuple[float, float]) -> tuple[int, int]:
    px, py = actor.get("display_position", position(actor))
    ox, oy = origin(camera)
    return round((px + 0.5) * TILE_PIXELS) - ox, round((py + 0.5) * TILE_PIXELS) - oy


def terrain(canvas: DotCanvas, game_map, camera: tuple[float, float], custom_tiles: dict, attributes: dict):
    ox, oy = origin(camera)
    first_x, first_y = math.floor(ox / TILE_PIXELS), math.floor(oy / TILE_PIXELS)
    last_x = math.ceil((ox + canvas.columns * 2) / TILE_PIXELS)
    last_y = math.ceil((oy + canvas.rows * 4) / TILE_PIXELS)
    for y in range(first_y, last_y):
        for x in range(first_x, last_x):
            override = custom_tiles.get(f"{x},{y}")
            tile = override["char"] if override else game_map.get_tile(x, y)
            if tile == game_map.AIR or tile == " ":
                continue
            canvas.rectangle(x * TILE_PIXELS - ox, y * TILE_PIXELS - oy, TILE_PIXELS, TILE_PIXELS,
                             attributes.get(tile, 0))


def actor_sprite(canvas: DotCanvas, actor: dict, camera: tuple[float, float], attr: int):
    cx, cy = project(actor, camera)
    moving = abs(float(actor.get("vx", 0))) > 0.01
    px, _ = actor.get("display_position", position(actor))
    feet = (-1, 1) if not moving else ((-1, 0) if int(px * 4) % 2 else (0, 1))
    for dx, dy in ((0, -2), (-1, -1), (0, -1), (1, -1), (0, 0), *((foot, 1) for foot in feet)):
        canvas.dot(cx + dx, cy + dy, attr, priority=2)


def tree_sprite(canvas: DotCanvas, actor: dict, camera: tuple[float, float], attr: int):
    cx, cy = project(actor, camera)
    for dy in range(-4, 2):
        canvas.dot(cx, cy + dy, attr, priority=1)
    for dy, half_width in ((-6, 0), (-5, 1), (-4, 2), (-3, 1)):
        for dx in range(-half_width, half_width + 1):
            canvas.dot(cx + dx, cy + dy, attr, priority=1)


def marker(canvas: DotCanvas, actor: dict, camera: tuple[float, float], attr: int):
    cx, cy = project(actor, camera)
    for offset in range(-2, 2):
        for dx, dy in ((offset, -2), (offset, 1), (-2, offset), (1, offset)):
            canvas.dot(cx + dx, cy + dy, attr, priority=3)

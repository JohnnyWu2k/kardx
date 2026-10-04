"""A 2x4 dot canvas gives terminal graphics movement within a character cell."""

import math
import curses

from ttx.world.physics import position
from ttx.world.sprites import load_sprite
from ttx.world.materials import material_attributes, pixel_cell, tile_stamp, merge_cell

DOT_BITS = ((1, 8), (2, 16), (4, 32), (64, 128))
BLOCKS = {0: " ", 255: "█", 71: "▌", 184: "▐", 27: "▀", 228: "▄"}
GLYPHS = tuple(BLOCKS.get(mask, chr(0x2800 + mask)) for mask in range(256))
TILE_PIXELS = 8
# One world tile = 8x8 addressable dots; one terminal cell = 2x4 dots.


def _pair_number(attr):
    # Decode the platform's attribute mask without requiring a live terminal.
    shift = (curses.A_COLOR & -curses.A_COLOR).bit_length() - 1
    return ((attr & curses.A_COLOR) >> shift) & 255


def _legacy_color(attr):
    return {2: 9, 3: 3, 4: 11, 5: 6, 6: 5, 7: 8, 8: 10, 10: 1}.get(_pair_number(attr), 3)


class DotCanvas:
    def __init__(self, rows: int, columns: int):
        self.rows, self.columns = rows, columns
        self.cells = [[(0, 0, -1) for _ in range(columns)] for _ in range(rows)]
        self.pixels = [[(-1,) * 8 for _ in range(columns)] for _ in range(rows)]

    def copy(self):
        result = object.__new__(DotCanvas)
        result.rows, result.columns = self.rows, self.columns
        result.cells = [row.copy() for row in self.cells]
        result.pixels = [row.copy() for row in self.pixels]
        return result

    def pixel(self, x: int, y: int, color: int):
        if 0 <= x < self.columns * 2 and 0 <= y < self.rows * 4:
            row, col = y // 4, x // 2
            values = list(self.pixels[row][col])
            values[(y % 4) * 2 + x % 2] = color
            self.pixels[row][col] = tuple(values)

    def dot(self, x: int, y: int, attr: int = 0, priority: int = 0):
        if not (0 <= x < self.columns * 2 and 0 <= y < self.rows * 4):
            return
        row, col = y // 4, x // 2
        mask, old_attr, old_priority = self.cells[row][col]
        bit = DOT_BITS[y % 4][x % 2]
        if priority >= old_priority:
            old_attr, old_priority = attr, priority
            self.pixel(x, y, _legacy_color(attr))
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
        for py in range(top, bottom):
            for px in range(left, right):
                self.pixel(px, py, _legacy_color(attr))

    def paint(self, frame):
        attributes = material_attributes()
        for y, row in enumerate(self.pixels):
            if y >= frame.rows:
                break
            target = frame.cells[y]
            for x, colors in enumerate(row):
                if x >= frame.columns:
                    break
                if colors == (-1,) * 8:
                    continue
                char, foreground, background = pixel_cell(colors)
                # Quadrants are always single-width and this layer precedes text.
                target[x] = char, attributes[foreground][background]

    def stamp(self, tile, x, y, left, top):
        for dx, dy, colors, complete in tile_stamp(tile, x % 2, y % 2, left % 2, top % 4):
            row, col = top // 4 + dy, left // 2 + dx
            if 0 <= row < self.rows and 0 <= col < self.columns:
                if complete:
                    self.pixels[row][col] = colors
                else:
                    old = self.pixels[row][col]
                    self.pixels[row][col] = merge_cell(colors, old)


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
            left, top = x * TILE_PIXELS - ox, y * TILE_PIXELS - oy
            attr = attributes.get(tile, 0)
            if tile == "W":
                canvas.rectangle(left + 1, top + 1, 7, 2, attr)
                canvas.rectangle(left + 2, top + 3, 1, 5, attr)
                canvas.rectangle(left + 6, top + 3, 1, 5, attr)
                continue
            # Filled, world-anchored material pixels: no dim pass, holes or seams.
            canvas.stamp(tile, x, y, left, top)


def actor_sprite(canvas: DotCanvas, actor: dict, camera: tuple[float, float], attr: int):
    cx, cy = project(actor, camera)
    facing = int(actor.get("facing", 1)) or 1
    pose = actor.get("pose", "idle")
    phase = int(actor.get("walk_frame", 0)) % 8
    body = {5: 6, 3: 3}.get(_pair_number(attr), 11)
    pixels = {}

    def block(x, y, width, height, color):
        for dy in range(height):
            for dx in range(width):
                pixels[x + dx, y + dy] = color

    crouch = pose == "land"
    head_y = 2 if crouch else 0
    block(2, head_y, 4, 2, 12)
    block(5, head_y, 1, 1, 0)  # The eye also makes facing legible at rest.
    block(2, 4 if crouch else 2, 4, 1 if crouch else 3, body)
    block(2, 5, 4, 1, 10)
    stride = (-2, -1, 0, 1, 2, 1, 0, -1)[phase] if pose == "walk" else 0
    if pose == "rise":
        block(1, 1, 1, 3, body)
        block(6, 2, 1, 2, body)
        block(1, 6, 2, 1, 10)
        block(5, 6, 2, 2, 10)
    elif pose == "fall":
        block(0, 2, 2, 1, body)
        block(6, 2, 2, 1, body)
        block(2, 6, 1, 2, 10)
        block(5, 6, 1, 2, 10)
    else:
        block(1, 4 if crouch else 3 + max(0, stride), 1, 2, body)
        block(6, 4 if crouch else 3 + max(0, -stride), 1, 2, body)
        # Passing feet lift on opposite halves of the cycle; the walk does not
        # simply ping-pong between the same two silhouettes.
        lift_front = -1 if pose == "walk" and phase in (1, 2, 3) else 0
        lift_back = -1 if pose == "walk" and phase in (5, 6, 7) else 0
        block(2 + min(0, stride), 6 + lift_back, 2, 2, 10)
        block(4 + max(0, stride), 6 + lift_front, 2, 2, 10)
    for (x, y), color in pixels.items():
        canvas.pixel(cx - 4 + (x if facing > 0 else 7 - x), cy - 4 + y, color)


def tree_sprite(canvas: DotCanvas, actor: dict, camera: tuple[float, float], attr: int):
    cx, cy = project(actor, camera)
    sprite = load_sprite("tree")
    sprite.blit(canvas, cx - sprite.width // 2, cy - sprite.height + 2)


def marker(canvas: DotCanvas, actor: dict, camera: tuple[float, float], attr: int):
    cx, cy = project(actor, camera)
    half = TILE_PIXELS // 2
    for offset in range(-half, half):
        for dx, dy in ((offset, -half), (offset, half - 1), (-half, offset), (half - 1, offset)):
            canvas.dot(cx + dx, cy + dy, attr, priority=3)

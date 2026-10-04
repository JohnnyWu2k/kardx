"""Seeded side-view terrain, generated in chunks from world coordinates."""

import math
import random

try:
    import curses
except ModuleNotFoundError:
    curses = None


class InfiniteGameMap:
    AIR = "."
    SOLID_TILES = frozenset({'"', ":", "#", "%", "o", "*", "|", "c", "l", "W"})

    def __init__(self, width: int, chunk_height: int = 20, seed: int | None = None,
                 height: int = 192, chunk_width: int = 32):
        self.width = max(1, width)
        self.height = max(48, height)
        self.chunk_height = max(1, chunk_height)
        self.chunk_width = max(1, chunk_width)
        self.seed = seed if seed is not None else random.randint(0, 1_000_000)
        self.chunks: dict[tuple[int, int], list[list[str]]] = {}
        self._surface_heights: dict[int, int] = {}

    def _hash(self, x: int, y: int, salt: int = 0) -> float:
        value = (x * 374761393 + y * 668265263 + self.seed * 1442695041 + salt * 1013904223) & 0xFFFFFFFF
        value = ((value ^ (value >> 13)) * 1274126177) & 0xFFFFFFFF
        return (value ^ (value >> 16)) / 0xFFFFFFFF

    def _noise(self, x: float, y: float, salt: int = 0) -> float:
        ix, iy = math.floor(x), math.floor(y)
        tx, ty = x - ix, y - iy
        tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
        a, b = self._hash(ix, iy, salt), self._hash(ix + 1, iy, salt)
        c, d = self._hash(ix, iy + 1, salt), self._hash(ix + 1, iy + 1, salt)
        return (a + (b - a) * tx) * (1 - ty) + (c + (d - c) * tx) * ty

    def surface_height(self, x: int) -> int:
        if x in self._surface_heights:
            return self._surface_heights[x]
        elevation = (self._noise(x / 96, 0, 1) - 0.5) * 18
        elevation += (self._noise(x / 32, 0, 2) - 0.5) * 8
        elevation += (self._noise(x / 12, 0, 3) - 0.5) * 3
        # Blend the level landing area into the surrounding hills.
        blend = min(1.0, max(0.0, (x - 12) / 12))
        height = round(22 + elevation * blend)
        self._surface_heights[x] = height
        return height

    def spawn_position(self) -> tuple[int, int]:
        x = min(5, self.width - 1)
        return x, self.surface_height(x) - 1

    def _generate_tile(self, x: int, y: int) -> str:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return " "
        if x in (0, self.width - 1) or y == self.height - 1:
            return "#"
        surface = self.surface_height(x)
        depth = y - surface
        if depth < 0:
            return self.AIR
        desert = x > 12 and self._noise(x / 120, 0, 11) > 0.64
        if depth == 0:
            return "%" if desert else '"'
        if depth < 5:
            return "%" if desert else ":"
        cave = self._noise(x / 15, y / 9, 20) * 0.7 + self._noise(x / 7, y / 5, 21) * 0.3
        tunnel_y = surface + 17 + round((self._noise(x / 28, 0, 22) - 0.5) * 10)
        if depth > 7 and (cave > 0.62 or abs(y - tunnel_y) <= 1):
            return self.AIR
        vein = self._noise(x / 5, y / 4, 30)
        if depth > 24 and vein > 0.79:
            return "*"
        if depth > 16 and self._noise(x / 4, y / 3, 32) > 0.72:
            return "l"
        if depth > 7 and vein > 0.69:
            return "o"
        if self._noise(x / 5, y / 4, 31) > 0.65:
            return "c"
        return "#"

    def generate_chunk(self, chunk_index: int, chunk_x: int = 0) -> list[list[str]]:
        chunk = [
            [self._generate_tile(chunk_x * self.chunk_width + x,
                                 chunk_index * self.chunk_height + y)
             for x in range(self.chunk_width)]
            for y in range(self.chunk_height)
        ]
        self.chunks[(chunk_x, chunk_index)] = chunk
        return chunk

    def get_chunk(self, chunk_index: int, chunk_x: int = 0) -> list[list[str]]:
        key = (chunk_x, chunk_index)
        return self.chunks[key] if key in self.chunks else self.generate_chunk(chunk_index, chunk_x)

    def get_tile(self, x: int, y: int) -> str:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return " "
        chunk_x, local_x = divmod(x, self.chunk_width)
        chunk_y, local_y = divmod(y, self.chunk_height)
        return self.get_chunk(chunk_y, chunk_x)[local_y][local_x]

    def is_walkable(self, x: int, y: int) -> bool:
        return self.get_tile(x, y) == self.AIR

    def draw_scaled(self, stdscr, scale: int = 1, camera_x: int = 0,
                    camera_y: int = 0, width_limit: int | None = None,
                    custom_tiles: dict | None = None):
        max_y, max_x = stdscr.getmaxyx()
        scale = max(1, scale)
        custom_tiles = custom_tiles or {}
        attributes = {tile: self._tile_attr(tile) for tile in self.SOLID_TILES}
        visible_cols = min(max_x, width_limit if width_limit is not None else max_x) // scale
        for sy in range(max_y // scale):
            gy = camera_y + sy
            for sx in range(visible_cols):
                gx = camera_x + sx
                override = custom_tiles.get(f"{gx},{gy}")
                tile = override["char"] if override else self.get_tile(gx, gy)
                char = " " if tile == self.AIR else tile[0]
                attr = attributes.get(tile, 0)
                for dy in range(scale):
                    for dx in range(scale):
                        try:
                            stdscr.addch(sy * scale + dy, sx * scale + dx, char, attr)
                        except curses.error:
                            pass

    def _tile_attr(self, tile: str) -> int:
        if curses is None:
            return 0
        pair = {'"': 2, ":": 6, "#": 3, "%": 7, "o": 7, "*": 4, "|": 6, "c": 10, "l": 8, "W": 6}.get(tile)
        return curses.color_pair(pair) if pair else curses.A_NORMAL

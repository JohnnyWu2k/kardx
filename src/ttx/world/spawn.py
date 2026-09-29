"""Place actors and trees on the generated side-view terrain."""

import random
from collections.abc import Iterable

from .map import InfiniteGameMap


def spawn_enemies(world_width: int, world_height: int, seed: int | None = None,
                  game_map: InfiniteGameMap | None = None) -> dict:
    rng = random.Random(seed)
    game_map = game_map or InfiniteGameMap(world_width, seed=seed)
    archetypes = ["enemy_giant_rat", "enemy_forest_wolf", "enemy_ancient_guardian"]
    enemies = {}
    for index, card_enemy_id in enumerate(archetypes):
        x = min(world_width - 2, 24 + index * 22 + rng.randint(0, 5))
        y = game_map.surface_height(x) - 1
        if x <= 1 or not game_map.is_walkable(x, y):
            continue
        enemies[f"enemy_{index + 1}"] = {
            "x": x, "y": y, "home_x": x, "direction": rng.choice([-1, 1]),
            "char": "E", "hp": 3, "mode": "patrol", "aggro_radius": 12,
            "vy": 0.0, "vertical_progress": 0.0,
            "card_enemy_id": card_enemy_id,
            "reward_cards": ["first_aid", "mana_gem", "double_strike"],
        }
    return enemies


def spawn_objects(world_width: int, world_height: int, seed: int | None = None,
                  game_map: InfiniteGameMap | None = None) -> dict:
    rng = random.Random(seed)
    game_map = game_map or InfiniteGameMap(world_width, seed=seed)
    objects = {}
    for grove in range(max(2, world_width // 45)):
        center = rng.randint(9, max(9, world_width - 10))
        for offset in range(rng.randint(2, 4)):
            x = center + offset * 2
            if not 1 <= x < world_width - 1:
                continue
            y = game_map.surface_height(x) - 1
            if game_map.is_walkable(x, y):
                objects[f"tree_{grove}_{x}"] = {
                    "x": x, "y": y, "char": "T", "type": "tree", "drop": "wood",
                }
    return objects


def object_at(objects: dict, positions: Iterable[tuple[int, int]]) -> tuple[str, dict] | None:
    position_set = set(positions)
    for object_id, obj in objects.items():
        if (obj.get("x"), obj.get("y")) in position_set:
            return object_id, obj
    return None

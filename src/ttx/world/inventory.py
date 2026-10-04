"""Stable item slots shared by the hotbar, backpack and saved player profile."""
HOTBAR_SIZE = 10
BACKPACK_SIZE = 25
BLOCKS = {"wood": "|", "stone": "#", "dirt": ":", "sand": "%", "workbench": "W"}
SYMBOLS = {**BLOCKS, "wood_pickaxe": "/", "stone_pickaxe": "/", "iron_pickaxe": "/",
           "iron_ore": "o", "coal": "c", "lead_ore": "l", "crystal_shard": "*", "stick": "!"}


def hotbar_key(key):
    if key in range(ord("1"), ord("9") + 1):
        return key - ord("1")
    return 9 if key == ord("0") else None


def sync_slots(slots, counts):
    result, assigned = [], set()
    for item in list(slots)[:BACKPACK_SIZE]:
        keep = item is not None and counts.get(item, 0) > 0 and item not in assigned
        result.append(item if keep else None)
        if keep:
            assigned.add(item)
    result.extend([None] * (BACKPACK_SIZE - len(result)))
    empty = iter(index for index, item in enumerate(result) if item is None)
    for item, count in counts.items():
        if count > 0 and item not in assigned:
            index = next(empty, None)
            if index is None:
                break
            result[index] = item
            assigned.add(item)
    return result


def valid_order(slots):
    if not isinstance(slots, list) or len(slots) != BACKPACK_SIZE:
        return False
    items = [item for item in slots if item is not None]
    return (all(isinstance(item, str) and 0 < len(item) <= 100 for item in items)
            and len(items) == len(set(items)))

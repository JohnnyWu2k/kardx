"""Shared item progression; the server owns all checks and inventory changes."""
TOOLS = {"wood_pickaxe": 1, "stone_pickaxe": 2, "iron_pickaxe": 3}
TILES = {
    '"': ("dirt", 0), ":": ("dirt", 0), "%": ("sand", 0), "|": ("wood", 0),
    "#": ("stone", 1), "o": ("iron_ore", 2), "c": ("coal", 1),
    "l": ("lead_ore", 2), "*": ("crystal_shard", 3), "W": ("workbench", 0),
}
RECIPES = {
    "sticks": ({"wood": 2}, "stick", 4, False),
    "workbench": ({"wood": 4}, "workbench", 1, False),
    "wood_pickaxe": ({"wood": 3, "stick": 2}, "wood_pickaxe", 1, True),
    "stone_pickaxe": ({"stone": 3, "stick": 2}, "stone_pickaxe", 1, True),
    "iron_pickaxe": ({"iron_ore": 3, "stick": 2}, "iron_pickaxe", 1, True),
}


def best_tool(inventory):
    return max((tool for tool in TOOLS if inventory.get(tool, 0) > 0), key=TOOLS.get, default=None)


def craft(inventory, recipe, near_bench):
    if recipe not in RECIPES:
        return "Unknown recipe"
    costs, item, amount, bench = RECIPES[recipe]
    if bench and not near_bench:
        return "Stand within 2 tiles of a placed workbench"
    if any(inventory.get(key, 0) < count for key, count in costs.items()):
        return "Not enough materials"
    for key, count in costs.items():
        inventory[key] -= count
    inventory[item] = inventory.get(item, 0) + amount
    return f"Crafted {amount} {item}"

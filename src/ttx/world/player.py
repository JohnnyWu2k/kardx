class Player:
    def __init__(self, x: int, y: int, char: str = "@"):
        self.x = x
        self.y = y
        self.char = char
        self.hp = 50
        self.gold = 0
        self.inventory: dict[str, int] = {}

    def add_item(self, item_id: str, amount: int = 1):
        current = self.inventory.get(item_id, 0) + amount
        if current <= 0:
            self.inventory.pop(item_id, None)
        else:
            self.inventory[item_id] = current

    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "char": self.char,
            "hp": self.hp,
            "gold": self.gold,
            "inventory": self.inventory,
        }

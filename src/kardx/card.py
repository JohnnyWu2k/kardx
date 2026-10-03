# src/card.py
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Card:
    """代表一張卡片的資料類別。"""
    id: str
    name: str
    cost: int
    type: str
    description: str
    effects: list[dict] = field(default_factory=list)
    rarity: str = "common"

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("Card id must be a nonempty string.")
        if type(self.cost) is not int or self.cost < 0:
            raise ValueError(f"Card '{self.id}' cost must be a nonnegative integer.")
        if not all(isinstance(value, str) for value in (self.name, self.type, self.description, self.rarity)):
            raise ValueError(f"Card '{self.id}' text fields must be strings.")
        if not isinstance(self.effects, list) or any(not isinstance(effect, dict) for effect in self.effects):
            raise ValueError(f"Card '{self.id}' effects must be a list of objects.")

    def __repr__(self) -> str:
        return f"{self.name} (費用:{self.cost})"

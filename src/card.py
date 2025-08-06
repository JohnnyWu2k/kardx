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

    def __repr__(self) -> str:
        return f"{self.name} (費用:{self.cost})"
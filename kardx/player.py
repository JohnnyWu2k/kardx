# src/player.py
import random
from .card import Card

class Player:
    """Represents a player or an enemy."""
    def __init__(self, name: str, hp: int, mana: int, deck: list[Card]):
        self.name = name
        self.max_hp = hp
        self.hp = hp
        self.max_mana = mana
        self.mana = 0
        self.block = 0
        self.deck = list(deck)
        self.hand: list[Card] = []
        self.discard_pile: list[Card] = []
        random.shuffle(self.deck)

    def draw_cards(self, num: int) -> bool:
        shuffled = False
        for _ in range(num):
            if not self.deck:
                if not self.discard_pile: break
                self.deck.extend(self.discard_pile)
                self.discard_pile.clear()
                random.shuffle(self.deck)
                shuffled = True
            if self.deck: self.hand.append(self.deck.pop())
        return shuffled

    def start_turn(self, draw_amount: int = 5) -> bool:
        self.mana = self.max_mana
        self.block = 0
        return self.draw_cards(draw_amount)

    def end_turn(self):
        self.discard_pile.extend(self.hand)
        self.hand.clear()
        
    def take_damage(self, amount: int):
        damage_after_block = max(0, amount - self.block)
        self.block = max(0, self.block - amount)
        self.hp -= damage_after_block

    def gain_block(self, amount: int):
        self.block += amount

    def gain_mana(self, amount: int):
        self.mana += amount
        self.max_mana += amount

        
    def gain_hp(self, amount: int) -> int:
        original_hp = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - original_hp
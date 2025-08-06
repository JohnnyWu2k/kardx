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
        self.defend = 0
        self.deck = list(deck)
        self.hand: list[Card] = []
        self.discard_pile: list[Card] = []
        random.shuffle(self.deck)

    def draw_cards(self, num: int) -> bool:
        # ... (no change) ...
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
        self.defend = 0
        return self.draw_cards(draw_amount)

    def end_turn(self):
        # ... (no change) ...
        self.discard_pile.extend(self.hand)
        self.hand.clear()
        
   ### MODIFIED: take_damage now returns a detailed report dictionary ###
    def take_damage(self, amount: int) -> dict:
        """
        Calculates damage, modifies state, and returns a detailed report.
        """
        damage_blocked = min(self.defend, amount)
        damage_dealt = amount - damage_blocked

        self.hp -= damage_dealt
        self.defend -= damage_blocked
        
        # Return a dictionary with all the details for the animation system
        return {
            'dealt': damage_dealt,
            'blocked': damage_blocked
        }

    def add_def(self, amount: int):
        self.defend += amount

    ### MODIFIED: Split mana logic ###
    def add_mana(self, amount: int):
        """Adds to current mana, capped by max_mana."""
        self.mana = min(self.max_mana, self.mana + amount)
        self.mana = max(0, self.mana) # Ensure it doesn't go below zero

    def add_max_mana(self, amount: int):
        """Adds to max_mana. Also gives current mana."""
        self.max_mana = max(0, self.max_mana + amount)
        
        
    def add_hp(self, amount: int) -> int:
        # ... (no change) ...
        original_hp = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - original_hp

    def set_hp(self, value: int):
        # ... (no change) ...
        self.hp = min(self.max_hp, value)

    def discard_card(self, card_index: int):
        # ... (no change) ...
        if 0 <= card_index < len(self.hand):
            card = self.hand.pop(card_index)
            self.discard_pile.append(card)
            return card
        return None
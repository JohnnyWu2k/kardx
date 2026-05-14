# src/player.py
import random
from .card import Card

class Player:
    def __init__(self, name: str, hp: int, mana: int, deck: list[Card]):
        # ... (attributes remain the same) ...
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

    ### MODIFIED: Draw logic ###
    def draw_cards(self, num_to_draw: int) -> bool:
        """Draws cards from the deck. Returns True if the deck was shuffled."""
        shuffled = False
        for _ in range(num_to_draw):
            if not self.deck:
                # If deck is empty, DO NOT reshuffle discard pile.
                # This enforces the finite deck rule.
                break 
            self.hand.append(self.deck.pop())
        return shuffled # This will likely always be False now, but we keep it for consistency.

    def start_turn(self, hand_limit: int = 5) -> bool:
        """
        Starts the turn, refills mana, resets defend, and draws until hand size is `hand_limit`.
        """
        self.mana = self.max_mana
        self.defend = 0
        
        cards_to_draw = hand_limit - len(self.hand)
        if cards_to_draw > 0:
            return self.draw_cards(cards_to_draw)
        return False

    ### MODIFIED: end_turn no longer discards the whole hand ###
    def end_turn(self):
        """
        Ends the turn. The hand is now kept.
        We can add logic here for effects that trigger at turn end.
        """
        pass # No longer discards hand

    ### NEW: Method to check for loss condition ###
    def is_out_of_cards(self) -> bool:
        """Check if the player has no cards left in hand or deck."""
        return not self.deck and not self.hand

    # ... (take_damage, add_def, etc. are unchanged from the last correct version) ...
    def take_damage(self, amount: int) -> dict:
        damage_blocked = min(self.defend, amount)
        damage_dealt = amount - damage_blocked
        self.hp -= damage_dealt
        self.defend -= damage_blocked
        return {'dealt': damage_dealt, 'blocked': damage_blocked}

    def add_def(self, amount: int): self.defend += amount
    def add_mana(self, amount: int): self.mana = min(self.max_mana, max(0, self.mana + amount))
    def add_max_mana(self, amount: int): self.max_mana = max(0, self.max_mana + amount)
    def add_hp(self, amount: int) -> int:
        original_hp = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - original_hp
    def set_hp(self, value: int): self.hp = min(self.max_hp, value)
    def discard_card(self, card_index: int):
        if 0 <= card_index < len(self.hand):
            card = self.hand.pop(card_index)
            self.discard_pile.append(card)
            return card
        return None
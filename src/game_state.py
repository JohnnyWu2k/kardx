# src/game_state.py
import re
import math
from pathlib import Path
from collections import deque
from .loader import load_json5_data
from .card import Card
from .player import Player

class Game:
    # __init__, _load_data, _create_character, _log, _evaluate_expression remain the same...
    def __init__(self, player_id: str, enemy_id: str):
        self.all_cards = self._load_data("cards.jsonc")
        self.character_definitions = self._load_data("characters.jsonc")
        self.player = self._create_character(player_id)
        self.enemy = self._create_character(enemy_id)
        self.is_running = False
        self.action_log = deque(maxlen=5)

    def _load_data(self, filename: str) -> dict:
        data = load_json5_data(Path("data") / filename)
        if not data: print(f"CRITICAL ERROR: Failed to load {filename}. Exiting."); return {}
        if filename == "cards.jsonc": return {item['id']: Card(**item) for item in data}
        return data

    def _create_character(self, character_id: str) -> Player | None:
        char_def = self.character_definitions.get(character_id)
        if not char_def: print(f"ERROR: Character '{character_id}' not found."); return None
        deck = []
        for card_id, count in char_def.get("deck", {}).items():
            if card_id in self.all_cards: deck.extend([self.all_cards[card_id]] * count)
            else: print(f"Warning: Card '{card_id}' not found.")
        return Player(name=char_def.get("display_name", "Unknown"), hp=char_def.get("hp", 10), mana=char_def.get("mana", 3), deck=deck)
    
    def _log(self, message: str):
        self.action_log.append(message)
    
    def _evaluate_expression(self, expr: int | str, source: Player, target: Player) -> int:
        if isinstance(expr, int): return expr
        expression_str = str(expr)
        def repl(match):
            obj_name, attr_str = match.group(1), match.group(2)
            if obj_name == 'self': obj = source
            elif obj_name == 'enemy': obj = target
            else: return "0"
            if obj and hasattr(obj, attr_str): return str(getattr(obj, attr_str))
            return "0"
        expression_str = re.sub(r'(self|enemy)\.(\w+)', repl, expression_str)
        try:
            match = re.match(r'^\s*(-?\d+)\s*([/*+-])\s*(-?\d+)\s*$', expression_str)
            if match:
                lhs, op, rhs = match.groups(); lhs, rhs = int(lhs), int(rhs)
                if op == '+': return lhs + rhs
                if op == '-': return lhs - rhs
                if op == '*': return lhs * rhs
                if op == '/' and rhs != 0: return math.ceil(lhs / rhs)
                return 0
            else: return int(expression_str)
        except (ValueError, TypeError): self._log(f"Warning: Could not parse expression '{expr}'"); return 0

    ### MODIFIED: Now returns a list of events for animation ###
    def _apply_effects(self, card: Card, source: Player, target: Player) -> list[dict]:
        self._log(f"{source.name} plays '{card.name}'!")
        events = []
        for effect in card.effects:
            eff_target_str = effect.get("target", "self")
            eff_target_obj = source if eff_target_str == "self" else target
            
            value = self._evaluate_expression(effect.get("value", 0), source, target)
            action = effect.get("action")

            if action == "deal_damage":
                # Get the detailed report from the method that actually changes the state
                damage_report = eff_target_obj.take_damage(value)
                damage_done = damage_report['dealt']
                blocked_amount = damage_report['blocked']
                
                self._log(f"It deals {damage_done} damage to {eff_target_obj.name}.")
                events.append({
                    'type': 'damage',
                    'target': eff_target_obj,
                    'value': damage_done,
                    'blocked': blocked_amount
                })
            
            elif action == "add_hp":
                # We need a similar report for add_hp to get before/after state
                hp_before = eff_target_obj.hp
                eff_target_obj.add_hp(value)
                hp_after = eff_target_obj.hp
                amount_changed = hp_after - hp_before

                if value >= 0:
                    self._log(f"{eff_target_obj.name} heals for {amount_changed} HP.")
                    events.append({'type': 'heal', 'target': eff_target_obj, 'value': amount_changed})
                else:
                    self._log(f"{eff_target_obj.name} takes {abs(amount_changed)} true damage!")
                    # True damage has 0 blocked
                    events.append({
                        'type': 'damage',
                        'target': eff_target_obj,
                        'value': abs(amount_changed),
                        'blocked': 0
                    })
            
            elif action == "add_def":
                eff_target_obj.add_def(value)
                self._log(f"{eff_target_obj.name} gains {value} DEF.")
                events.append({'type': 'defend', 'target': eff_target_obj, 'value': value})
            
            elif action == "add_mana":
                mana_before = eff_target_obj.mana
                eff_target_obj.add_mana(value)
                mana_gained = eff_target_obj.mana - mana_before
                if mana_gained > 0:
                    self._log(f"{eff_target_obj.name} gains {mana_gained} Mana.")
                    events.append({'type': 'mana_gain', 'target': eff_target_obj, 'value': mana_gained})

            elif action == "add_max_mana":
                eff_target_obj.add_max_mana(value)
                self._log(f"{eff_target_obj.name}'s Max Mana is now {eff_target_obj.max_mana}.")
                events.append({'type': 'max_mana_gain', 'target': eff_target_obj, 'value': value})
            else:
                self._log(f"Warning: Unknown action '{action}' in card '{card.name}'")
        
        return events

    ### MODIFIED: Battle now starts with both players drawing cards ###
    def start_battle(self):
        """Initializes the battle state, including initial card draw."""
        if self.player and self.enemy:
            self.is_running = True
            self._log(f"A wild {self.enemy.name} appears!")
            
            # Both players draw their starting hands at the very beginning
            self.player.draw_cards(5)
            self.enemy.draw_cards(5)
            self._log(f"{self.player.name} and {self.enemy.name} draw their starting hands.")


    def start_player_turn(self):
        """Prepares for the player's turn."""
        # The hand limit is now passed to the player method
        # We no longer need the initial draw here, as it's done in start_battle
        # The start_turn method will handle refilling mana and resetting defend
        self.player.start_turn(hand_limit=5)
        self._log(f"--- Player's Turn ---")
    
    def end_player_turn(self):
        # ... (no change) ...
        self._log("Player ends their turn.")
        self.player.end_turn()

    ### MODIFIED: Returns events from _apply_effects ###
    def play_card(self, card_index: int) -> tuple[str, list[dict]]:
        """Attempts to play a card. Returns a status and a list of animation events."""
        if not 0 <= card_index < len(self.player.hand):
            return "invalid_card", []
        
        card_to_play = self.player.hand[card_index]
        if self.player.mana < card_to_play.cost:
            self._log("Not enough Mana!")
            return "not_enough_mana", []
        
        self.player.mana -= card_to_play.cost
        played_card = self.player.hand.pop(card_index)
        # Get events from applying effects
        events = self._apply_effects(played_card, self.player, self.enemy)
        self.player.discard_pile.append(played_card)
        
        if self.enemy.hp <= 0:
            self.is_running = False
            self._log(f"{self.enemy.name} has been defeated!")
        
        return "success", events

    ### REFACTORED: Enemy turn logic is now controller-driven ###
    def start_enemy_turn(self):
        """Only prepares the enemy's turn."""
        if not self.is_running: return
        self.enemy.start_turn(hand_limit=5)
        self._log(f"--- Enemy's Turn ---")

    def get_enemy_playable_card(self) -> Card | None:
        """Finds one playable card from the enemy's hand."""
        if not self.is_running: return None
        return next((c for c in self.enemy.hand if self.enemy.mana >= c.cost), None)

    def play_enemy_card(self, card: Card) -> list[dict]:
        """Executes a single enemy card play and returns animation events."""
        if not self.is_running: return []
        self.enemy.mana -= card.cost
        self.enemy.hand.remove(card)
        events = self._apply_effects(card, self.enemy, self.player)
        self.enemy.discard_pile.append(card)
        
        if self.player.hp <= 0:
            self.is_running = False
            self._log(f"{self.player.name} has been defeated!")
        return events

    def end_enemy_turn(self):
        """Cleans up after the enemy's turn."""
        if not self.is_running: return
        self.enemy.end_turn()
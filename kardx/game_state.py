# src/game_state.py
import time
from pathlib import Path
from collections import deque
from .loader import load_json5_data
from importlib import resources
from .card import Card
from .player import Player
from .view import CLIView

class Game:
    ### MODIFIED ###
    # __init__ now accepts player_id and enemy_id from main.py
    def __init__(self, player_id: str, enemy_id: str):
        self.all_cards = self._load_data("cards.jsonc")
        self.character_definitions = self._load_data("characters.jsonc")
        
        self.player = self._create_character(player_id)
        self.enemy = self._create_character(enemy_id)
        
        self.is_running = bool(self.player and self.enemy)
        self.view = CLIView()
        self.action_log = deque(maxlen=5)

    def _load_data(self, filename: str) -> dict:
        """通用資料載入器，從套件內部讀取資料。"""
        try:
            # 安全地找到套件內的 data 資料夾和目標檔案
            file_path = resources.files('kardx.data').joinpath(filename)
            data = load_json5_data(file_path)
            if not data:
                print(f"CRITICAL ERROR: Data in {filename} is empty or invalid.")
                return {}
            
            if filename == "cards.jsonc":
                 return {item['id']: Card(**item) for item in data}
            return data
        except (FileNotFoundError, ModuleNotFoundError):
            print(f"CRITICAL ERROR: Could not find data module 'xxcard.data' or file '{filename}'.")
            return {}

    def _create_character(self, character_id: str) -> Player | None:
        char_def = self.character_definitions.get(character_id)
        if not char_def:
            print(f"ERROR: Character '{character_id}' not found.")
            return None
        deck_composition = char_def.get("deck", {})
        starting_deck = []
        for card_id, count in deck_composition.items():
            if card_id in self.all_cards:
                starting_deck.extend([self.all_cards[card_id]] * count)
            else:
                print(f"Warning: Card '{card_id}' not found.")
        return Player(
            name=char_def.get("display_name", "Unknown"),
            hp=char_def.get("hp", 10),
            mana=char_def.get("mana", 1),
            deck=starting_deck
        )

    # _log, _apply_effects, _player_turn, _enemy_turn, run methods remain unchanged
    def _log(self, message: str):
        self.action_log.append(message)

    def _apply_effects(self, card: Card, source: Player, target: Player):
        self._log(f"{source.name} plays '{card.name}'!")
        for effect in card.effects:
            action, value = effect.get("action"), effect.get("value", 0)
            eff_target = target if effect.get("target") == "enemy" else source
            if action == "deal_damage":
                original_hp = eff_target.hp
                eff_target.take_damage(value)
                self._log(f"It deals {original_hp - eff_target.hp} damage to {eff_target.name}.")
            elif action == "gain_block":
                eff_target.gain_block(value)
                self._log(f"{eff_target.name} gains {value} DEF.")
            elif action == "boost_mana":
                eff_target.gain_mana(value)
                self._log(f"{eff_target.name}'s Max Mana is now {eff_target.max_mana}, gains {value} Mana!")
            elif action == "deal_damage_from_block":
                damage = source.block
                if damage > 0:
                    original_hp = eff_target.hp
                    eff_target.take_damage(damage)
                    self._log(f"Deals {original_hp - eff_target.hp} damage from DEF!")
                else:
                    self._log("No DEF to deal damage with.")
        self.view.display_board(self.player, self.enemy, self.action_log)
        time.sleep(1.2)

    def _player_turn(self):
        shuffled = self.player.start_turn(5)
        if shuffled: self._log("Player's deck empty. Shuffling discard pile!")
        self._log(f"--- Player's Turn ---")
        while self.is_running:
            self.view.display_board(self.player, self.enemy, self.action_log)
            action = self.view.get_player_input(len(self.player.hand))
            if action == 'e': self._log("Player ends their turn."); break
            try:
                card_index = int(action) - 1
                if not 0 <= card_index < len(self.player.hand): self._log("Invalid selection!"); time.sleep(1); continue
                card_to_play = self.player.hand[card_index]
                if self.player.mana < card_to_play.cost: self._log("Not enough Mana!"); time.sleep(1); continue
                self.player.mana -= card_to_play.cost
                played_card = self.player.hand.pop(card_index)
                self._apply_effects(played_card, self.player, self.enemy)
                self.player.discard_pile.append(played_card)
                if self.enemy.hp <= 0: self.is_running = False
            except ValueError: self._log("Invalid input."); time.sleep(1)
        self.player.end_turn()

    def _enemy_turn(self):
        if not self.is_running: return
        shuffled = self.enemy.start_turn(5)
        if shuffled: self._log("Enemy's deck empty. Shuffling discard pile!")
        self._log(f"--- Enemy's Turn ---")
        self.view.display_board(self.player, self.enemy, self.action_log)
        time.sleep(1.5)
        card_to_play = next((c for c in self.enemy.hand if self.enemy.mana >= c.cost), None)
        if card_to_play:
            self.enemy.mana -= card_to_play.cost
            self.enemy.hand.remove(card_to_play)
            self._apply_effects(card_to_play, self.enemy, self.player)
        else:
            self._log(f"{self.enemy.name} does nothing."); time.sleep(1)
        if self.player.hp <= 0: self.is_running = False
        self.enemy.end_turn()

    def run(self):
        if not self.is_running: return
        self._log(f"A wild {self.enemy.name} appears!")
        while self.is_running:
            self._player_turn()
            if not self.is_running: break
            self._enemy_turn()
        self.view.display_board(self.player, self.enemy, self.action_log)
        print("\n" + "="*25)
        if self.player.hp <= 0: print("      YOU WERE DEFEATED")
        elif self.enemy.hp <= 0: print("      VICTORY!")
        print("="*25)
# src/scenes/game/game_controller.py
import time
import os # <-- Import os to get terminal size here
from ...game_state import Game
from .game_view import GameView
from ...keyboard import get_key, KEY_LEFT, KEY_RIGHT, KEY_ENTER, KEY_ESC, KEY_E
from ...player import Player
from ..pause_menu.pause_menu_controller import PauseMenuController

class GameController:
    # ... __init__ and run methods are fine ...
    def __init__(self, game: Game, view: GameView):
        self.game = game
        self.view = view
        self.selected_card_index = 0

    def run(self) -> str:
        self.game.start_battle()
        # Initial draw before the loop starts
        self.view.display_board(self.game.player, self.game.enemy, self.game.action_log)

        while self.game.is_running:
            # ... loss condition checks ...
            
            turn_result = self.handle_player_turn()

            if turn_result == "quit_to_menu":
                return "main_menu" 
            if not self.game.is_running:
                break
            
            self.execute_enemy_turn_step_by_step()

        # ... game over logic ...
        self.view.display_board(self.game.player, self.game.enemy, self.game.action_log)
        self.view.display_game_over(self.game.player, self.game.enemy)
        return "victory" if self.game.player.hp > 0 else "defeat"


    def handle_player_turn(self):
        self.game.start_player_turn()
        # Redraw once at the beginning of the turn
        self.view.display_board(
            self.game.player, self.game.enemy, self.game.action_log,
            selected_index=self.selected_card_index
        )

        while True:
            key = get_key()
            
            # Default to no redraw
            needs_redraw = False

            if key == KEY_LEFT:
                if self.selected_card_index > 0: 
                    self.selected_card_index -= 1
                    needs_redraw = True
            elif key == KEY_RIGHT:
                if self.game.player.hand and self.selected_card_index < len(self.game.player.hand) - 1:
                    self.selected_card_index += 1
                    needs_redraw = True
            elif key == KEY_ENTER:
                if self.selected_card_index != -1:
                    status, events = self.game.play_card(self.selected_card_index)
                    if status == "success":
                        # The animation itself will handle redraws
                        self.view.play_animation(self.game.player, self.game.enemy, self.game.action_log, events)
                        if not self.game.is_running: return "game_over"
                        if not self.game.player.hand: self.selected_card_index = -1
                        else: self.selected_card_index = min(self.selected_card_index, len(self.game.player.hand) - 1)
                        # After animation, we need a final redraw of the stable state
                        needs_redraw = True
            elif key == KEY_E:
                self.game.end_player_turn()
                return "turn_ended"
            
            ### MODIFIED PAUSE LOGIC ###
            elif key == KEY_ESC:
                pause_controller = PauseMenuController()
                # The game screen is already drawn and visible here.
                # We now call the pause controller, which will draw ON TOP.
                pause_result = pause_controller.run()
                
                if pause_result == "main_menu":
                    return "quit_to_menu" # New signal
                # If "resume", we must redraw the screen to erase the pause menu.
                needs_redraw = True

            if needs_redraw:
                self.view.display_board(
                    self.game.player,
                    self.game.enemy,
                    self.game.action_log,
                    selected_index=self.selected_card_index
                )
    
    def execute_enemy_turn_step_by_step(self):
        # This method is fine, as its sleeps and redraws are self-contained.
        # ... no changes needed here ...
        if not self.game.is_running: return
        self.game.start_enemy_turn()
        self.view.display_board(self.game.player, self.game.enemy, self.game.action_log)
        time.sleep(1.0)
        while self.game.is_running:
            card_to_play = self.game.get_enemy_playable_card()
            if not card_to_play: break
            try:
                played_card_index = self.game.enemy.hand.index(card_to_play)
                self.view.display_board(
                    self.game.player, self.game.enemy, self.game.action_log,
                    enemy_card_played_index=played_card_index
                )
            except ValueError:
                self.view.display_board(self.game.player, self.game.enemy, self.game.action_log)
            time.sleep(1.5)
            events = self.game.play_enemy_card(card_to_play)
            self.view.play_animation(self.game.player, self.game.enemy, self.game.action_log, events)
            self.view.display_board(self.game.player, self.game.enemy, self.game.action_log)
        self.game.end_enemy_turn()
        self.view.display_board(self.game.player, self.game.enemy, self.game.action_log)
        time.sleep(1.0)
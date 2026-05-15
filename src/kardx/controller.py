# src/controller.py
from .game_state import Game
from .view import CLIView
from .keyboard import get_key, KEY_LEFT, KEY_RIGHT, KEY_ENTER, KEY_ESC, KEY_E, KEY_Q

class GameController:
    """Handles user input, animations, and drives the game forward."""

    def __init__(self, game: Game, view: CLIView):
        self.game = game
        self.view = view
        self.selected_card_index = 0

    def run_game(self) -> str | None:
        """The main loop for the entire game session."""
        self.game.start_battle()
        
        while self.game.is_running:
            turn_result = self.handle_player_turn()
            if turn_result == "quit":
                return "quit"

            if not self.game.is_running:
                break
            
            self.execute_enemy_turn()

        # After the loop (game over)
        self.view.display_board(self.game.player, self.game.enemy, self.game.action_log)
        self.view.display_game_over(self.game.player, self.game.enemy)
        return "finished"

    def handle_player_turn(self):
        """The event loop for a single player turn."""
        self.game.start_player_turn()
        self._normalize_selected_card_index()

        # Initial draw for the turn, no animation yet
        self.view.display_board(
            self.game.player, self.game.enemy, self.game.action_log,
            selected_index=self.selected_card_index
        )

        while True:
            key = get_key()
            action_taken = False

            if key == KEY_LEFT:
                if self.selected_card_index > 0:
                    self.selected_card_index -= 1
                    action_taken = True
            
            elif key == KEY_RIGHT:
                if self.game.player.hand and self.selected_card_index < len(self.game.player.hand) - 1:
                    self.selected_card_index += 1
                    action_taken = True
            
            elif key == KEY_ENTER:
                if self.selected_card_index != -1:
                    status, events = self.game.play_card(self.selected_card_index)
                    
                    if status == "success":
                        # Play animation for the successful card play
                        self.view.play_animation(self.game.player, self.game.enemy, self.game.action_log, events)

                        if not self.game.is_running:
                            return "game_over"
                        
                        # Update selection after playing a card
                        if not self.game.player.hand:
                            self.selected_card_index = -1
                        else:
                            self.selected_card_index = min(self.selected_card_index, len(self.game.player.hand) - 1)
                        action_taken = True
                    elif status == "not_enough_mana":
                        # We can add a "shake" or "error" animation here in the future
                        pass

            elif key == KEY_Q:
                if self.selected_card_index != -1:
                    status = self.game.discard_player_card(self.selected_card_index)
                    if status == "success":
                        self._normalize_selected_card_index()
                        action_taken = True

            elif key == KEY_E:
                self.game.end_player_turn()
                return "turn_ended"

            elif key == KEY_ESC:
                self.game.is_running = False
                return "quit"

            if action_taken:
                # Redraw the board with the updated selection
                self.view.display_board(
                    self.game.player,
                    self.game.enemy,
                    self.game.action_log,
                    selected_index=self.selected_card_index
                )

    def _normalize_selected_card_index(self):
        if not self.game.player.hand:
            self.selected_card_index = -1
            return
        if self.selected_card_index < 0:
            self.selected_card_index = 0
            return
        self.selected_card_index = min(self.selected_card_index, len(self.game.player.hand) - 1)

    def execute_enemy_turn(self):
        if not self.game.is_running:
            return
        self.game.start_enemy_turn()
        while self.game.is_running:
            card_to_play = self.game.get_enemy_playable_card()
            if not card_to_play:
                break
            events = self.game.play_enemy_card(card_to_play)
            self.view.play_animation(self.game.player, self.game.enemy, self.game.action_log, events)
        self.game.end_enemy_turn()

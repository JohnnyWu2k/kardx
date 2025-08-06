# src/controller.py
from .game_state import Game
from .view import CLIView
from .keyboard import get_key, KEY_LEFT, KEY_RIGHT, KEY_ENTER, KEY_ESC, KEY_E

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
            
            # The enemy turn logic is now cleaner
            enemy_events = self.game.execute_enemy_turn()
            self.view.play_animation(self.game.player, self.game.enemy, self.game.action_log, enemy_events)

        # After the loop (game over)
        self.view.display_board(self.game.player, self.game.enemy, self.game.action_log)
        self.view.display_game_over(self.game.player, self.game.enemy)
        return "finished"

    def handle_player_turn(self):
        """The event loop for a single player turn."""
        self.game.start_player_turn()
        self.selected_card_index = 0 if self.game.player.hand else -1

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
# src/scenes/game/game_controller.py
import time
from ...game_state import Game
from .game_view import GameView
from ...keyboard import get_key, get_key_non_blocking, KEY_LEFT, KEY_RIGHT, KEY_ENTER, KEY_ESC, KEY_E, KEY_Q
from ..pause_menu.pause_menu_controller import PauseMenuController

class GameController:
    # ... __init__ and run methods are fine ...
    def __init__(self, game: Game, view: GameView):
        self.game = game
        self.view = view
        self.selected_card_index = 0
        self.quit_to_menu_requested = False

    def run(self) -> str:
        if not self.game.player or not self.game.enemy:
            return "main_menu"
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
            
            enemy_turn_result = self.execute_enemy_turn_step_by_step()
            if enemy_turn_result == "quit_to_menu":
                return "main_menu"

        # ... game over logic ...
        self.view.display_board(self.game.player, self.game.enemy, self.game.action_log)
        self.view.display_game_over(self.game.player, self.game.enemy)
        return "victory" if self.game.player.hp > 0 else "defeat"


    def handle_player_turn(self):
        self.game.start_player_turn()
        self._normalize_selected_card_index()
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
                        if not self.game.player.hand: self.selected_card_index = -1
                        else: self.selected_card_index = min(self.selected_card_index, len(self.game.player.hand) - 1)
                        self.selected_card_index = self.view.play_animation(
                            self.game.player,
                            self.game.enemy,
                            self.game.action_log,
                            events,
                            selected_index=self.selected_card_index,
                            on_tick=self._handle_animation_input,
                            should_stop=lambda: self.quit_to_menu_requested,
                        )
                        if self.quit_to_menu_requested:
                            return "quit_to_menu"
                        if not self.game.is_running: return "game_over"
                        # After animation, we need a final redraw of the stable state
                        needs_redraw = True
            elif key == KEY_Q:
                if self.selected_card_index != -1:
                    status = self.game.discard_player_card(self.selected_card_index)
                    if status == "success":
                        self._normalize_selected_card_index()
                        needs_redraw = True
            elif key == KEY_E:
                self.game.end_player_turn()
                return "turn_ended"
            
            ### MODIFIED PAUSE LOGIC ###
            elif key == KEY_ESC:
                if self._run_pause_menu() == "main_menu":
                    return "quit_to_menu"
                needs_redraw = True

            if needs_redraw:
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

    def _handle_animation_input(self, selected_index: int | None) -> int | None:
        key = get_key_non_blocking()
        if key == KEY_ESC:
            self._run_pause_menu()
            return selected_index
        if key == KEY_LEFT and selected_index is not None and selected_index > 0:
            return selected_index - 1
        if (
            key == KEY_RIGHT
            and selected_index is not None
            and self.game.player.hand
            and selected_index < len(self.game.player.hand) - 1
        ):
            return selected_index + 1
        return selected_index

    def _run_pause_menu(self) -> str:
        pause_controller = PauseMenuController()
        pause_result = pause_controller.run()
        if pause_result == "main_menu":
            self.quit_to_menu_requested = True
            self.game.is_running = False
            self.game.action_log.clear()
            return "main_menu"
        self.view.display_board(
            self.game.player,
            self.game.enemy,
            self.game.action_log,
            selected_index=self.selected_card_index if self.game.player.hand else None,
        )
        return "resume"

    def _handle_enemy_turn_input(self, selected_index: int | None = None) -> int | None:
        key = get_key_non_blocking()
        if key == KEY_ESC:
            self._run_pause_menu()
        return selected_index

    def _wait_with_pause(self, duration: float) -> str:
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline and self.game.is_running:
            self._handle_enemy_turn_input()
            if self.quit_to_menu_requested:
                return "quit_to_menu"
            time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        return "continue"
    
    def execute_enemy_turn_step_by_step(self) -> str:
        if not self.game.is_running: return "continue"
        self.game.start_enemy_turn()
        self.view.display_board(self.game.player, self.game.enemy, self.game.action_log)
        if self._wait_with_pause(1.0) == "quit_to_menu":
            return "quit_to_menu"
        while self.game.is_running:
            card_to_play = self.game.get_enemy_playable_card()
            if not card_to_play: break
            played_card_index = None
            try:
                played_card_index = self.game.enemy.hand.index(card_to_play)
                self.view.display_board(
                    self.game.player, self.game.enemy, self.game.action_log,
                    enemy_card_played_index=played_card_index
                )
            except ValueError:
                self.view.display_board(self.game.player, self.game.enemy, self.game.action_log)
            if self._wait_with_pause(1.5) == "quit_to_menu":
                return "quit_to_menu"
            events = self.game.play_enemy_card(card_to_play)
            self.view.play_animation(
                self.game.player,
                self.game.enemy,
                self.game.action_log,
                events,
                on_tick=self._handle_enemy_turn_input,
                should_stop=lambda: self.quit_to_menu_requested,
            )
            if self.quit_to_menu_requested:
                return "quit_to_menu"
            self.view.display_board(self.game.player, self.game.enemy, self.game.action_log)
        self.game.end_enemy_turn()
        self.view.display_board(self.game.player, self.game.enemy, self.game.action_log)
        if self._wait_with_pause(1.0) == "quit_to_menu":
            return "quit_to_menu"
        return "continue"

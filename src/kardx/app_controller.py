# src/app_controller.py
from typing import Optional, Union
# We need all our scene controllers
from .scenes.main_menu.menu_controller import MainMenuController
from .scenes.game.game_controller import GameController
from .scenes.character_select.character_select_controller import CharacterSelectController
from .scenes.settings.settings_controller import SettingsController
from .scenes.adventure.adventure_controller import AdventureController
from .scenes.sandbox.sandbox_controller import SandboxController
# Import the actual models and views needed for creation
from .game_state import Game
from .scenes.game.game_view import GameView
from .scenes.editor.editor_app_controller import EditorAppController


class AppController:
    def __init__(self):
        self.active_scene_controller: Optional[Union[
            MainMenuController, 
            GameController, 
            CharacterSelectController, 
            SettingsController,
            AdventureController,
            SandboxController,
            EditorAppController # Now we only need to know about this one
        ]] = None
        self.pending_start_mode = "adventure"

    def run(self):
        self.active_scene_controller = MainMenuController()
        while self.active_scene_controller is not None:
            next_signal = self.active_scene_controller.run()
            
            # --- Simplified Scene Transition Logic ---
            if isinstance(next_signal, str) and next_signal.startswith("player_"):
                if self.pending_start_mode == "quick_battle":
                    self.active_scene_controller = self.start_game_session(next_signal)
                elif self.pending_start_mode == "sandbox":
                    self.active_scene_controller = self.start_sandbox_session(next_signal)
                else:
                    self.active_scene_controller = self.start_adventure_session(next_signal)
            elif next_signal == "sandbox_mode":
                self.pending_start_mode = "sandbox"
                self.active_scene_controller = CharacterSelectController()
            elif next_signal == "adventure_mode":
                self.pending_start_mode = "adventure"
                self.active_scene_controller = CharacterSelectController()
            elif next_signal == "quick_battle":
                self.pending_start_mode = "quick_battle"
                self.active_scene_controller = CharacterSelectController()
            elif next_signal == "settings":
                self.active_scene_controller = SettingsController()
            
            # --- NEW: Launching the entire editor subsystem ---
            elif next_signal == "editor":
                self.active_scene_controller = EditorAppController()
            
            elif next_signal in ["victory", "defeat"]:
                self.active_scene_controller = self.handle_game_over()
            elif next_signal == "main_menu":
                self.active_scene_controller = MainMenuController()
            elif next_signal == "quit":
                self.active_scene_controller = None
            else:
                print(f"Warning: Unknown signal '{next_signal}'. Returning to main menu.")
                self.active_scene_controller = MainMenuController()
        
        print("\nThanks for playing!")

    def start_adventure_session(self, player_id: str) -> Union[AdventureController, MainMenuController]:
        try:
            return AdventureController(player_id=player_id)
        except Exception as exc:
            print("\n" + "="*50)
            print("FATAL ERROR: Failed to initialize adventure mode.")
            print(f"  - {exc}")
            print("Please check adventures.jsonc, events.jsonc, relics.jsonc, and characters.jsonc.")
            print("="*50)
            input("Press Enter to return to the main menu...")
            return MainMenuController()

    def start_sandbox_session(self, player_id: str) -> Union[SandboxController, MainMenuController]:
        try:
            return SandboxController(player_id=player_id)
        except Exception as exc:
            print("\n" + "="*50)
            print("FATAL ERROR: Failed to initialize sandbox mode.")
            print(f"  - {exc}")
            print("Please check world.jsonc, recipes.jsonc, encounters.jsonc, cards.jsonc, and characters.jsonc.")
            print("="*50)
            input("Press Enter to return to the main menu...")
            return MainMenuController()

    def start_game_session(self, player_id: str) -> Union[GameController, MainMenuController]:
        """Creates the Game model and, if successful, the GameController."""
        
        print("Loading game...") # Provide feedback to the user
        game_model = Game(player_id=player_id, enemy_id="enemy_automaton")
        
        # --- ROBUSTNESS CHECK (Most important part) ---
        if not game_model.player or not game_model.enemy:
            # This block will now catch the error before the game controller is even created.
            print("\n" + "="*50)
            print("FATAL ERROR: Failed to initialize game characters.")
            if not game_model.player:
                print(f"  - Could not create player with ID: '{player_id}'")
            if not game_model.enemy:
                print(f"  - Could not create enemy with ID: 'enemy_automaton'")
            print("Please check characters.jsonc for missing entries or syntax errors.")
            print("="*50)
            input("Press Enter to return to the main menu...")
            return MainMenuController()

        # If we passed the check, it's safe to create the view and controller
        game_view = GameView()
        return GameController(game_model, game_view)
            
    def handle_game_over(self) -> Union[CharacterSelectController, MainMenuController]:
        """Asks the player to play again after a game ends."""
        while True:
            play_again = input("Play again? (y/n): ").strip().lower()
            if play_again == 'y':
                return CharacterSelectController()
            elif play_again == 'n':
                return MainMenuController()
            print("Invalid input. Please enter 'y' or 'n'.")

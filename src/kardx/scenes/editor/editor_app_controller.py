# src/scenes/editor/editor_app_controller.py
from typing import Optional, Union
# Import all controllers that belong to the editor subsystem
from .editor_menu_controller import EditorMenuController
from .card_editor_controller import CardEditorController
from .character_editor_controller import CharacterEditorController
from .data_file_editor_controller import DataFileEditorController

class EditorAppController:
    """The main controller for the entire editor subsystem."""
    def __init__(self):
        self.active_scene_controller: Optional[Union[
            EditorMenuController,
            CardEditorController,
            CharacterEditorController,
            DataFileEditorController,
        ]] = None

    def run(self) -> str:
        """
        Runs the editor's main loop.
        Returns a signal to the main AppController when the editor is exited.
        """
        # The editor always starts with its own main menu
        self.active_scene_controller = EditorMenuController()

        while self.active_scene_controller is not None:
            # Get the next signal from the current editor scene
            next_signal = self.active_scene_controller.run()

            # --- Editor-Internal Scene Transition Logic ---
            if next_signal == "character_editor":
                self.active_scene_controller = CharacterEditorController()
            elif next_signal == "card_editor":
                self.active_scene_controller = CardEditorController()
            elif next_signal == "adventure_editor":
                self.active_scene_controller = DataFileEditorController("adventures.jsonc", "adventure")
            elif next_signal == "event_editor":
                self.active_scene_controller = DataFileEditorController("events.jsonc", "event")
            elif next_signal == "relic_editor":
                self.active_scene_controller = DataFileEditorController("relics.jsonc", "relic")
            elif next_signal == "world_editor":
                self.active_scene_controller = DataFileEditorController("world.jsonc", "sandbox world")
            elif next_signal == "recipe_editor":
                self.active_scene_controller = DataFileEditorController("recipes.jsonc", "sandbox recipe")
            elif next_signal == "encounter_editor":
                self.active_scene_controller = DataFileEditorController("encounters.jsonc", "sandbox encounter")
            elif next_signal == "editor_menu":
                self.active_scene_controller = EditorMenuController()
            elif next_signal == "main_menu":
                # This is the signal to exit the editor subsystem
                self.active_scene_controller = None

        # When the loop ends, return to the main application's menu
        return "main_menu"

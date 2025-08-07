# src/scenes/editor/editor_app_controller.py
from typing import Optional, Union
# Import all controllers that belong to the editor subsystem
from .editor_menu_controller import EditorMenuController
from .card_editor_controller import CardEditorController
from .character_editor_controller import CharacterEditorController

class EditorAppController:
    """The main controller for the entire editor subsystem."""
    def __init__(self):
        self.active_scene_controller: Optional[Union[
            EditorMenuController,
            CardEditorController,
            CharacterEditorController
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
            elif next_signal == "editor_menu":
                self.active_scene_controller = EditorMenuController()
            elif next_signal == "main_menu":
                # This is the signal to exit the editor subsystem
                self.active_scene_controller = None

        # When the loop ends, return to the main application's menu
        return "main_menu"
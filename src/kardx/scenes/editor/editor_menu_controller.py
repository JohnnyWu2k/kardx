# src/scenes/editor/editor_menu_controller.py
from .editor_menu_view import EditorMenuView
from ...keyboard import get_key, KEY_UP, KEY_DOWN, KEY_ENTER, KEY_ESC

class EditorMenuController:
    """Handles logic for the editor's main menu."""
    def __init__(self):
        self.options = [
            "Edit Characters",
            "Edit Cards",
            "Edit Adventures",
            "Edit Events",
            "Edit Relics",
            "Edit Sandbox World",
            "Edit Sandbox Recipes",
            "Edit Sandbox Encounters",
            "Back to Main Menu",
        ]
        self.view = EditorMenuView(self.options)
        self.selected_index = 0

    def run(self) -> str:
        """Runs the loop and returns the next scene signal."""
        while True:
            self.view.display(self.selected_index)
            key = get_key()

            if key == KEY_UP:
                self.selected_index = (self.selected_index - 1) % len(self.options)
            elif key == KEY_DOWN:
                self.selected_index = (self.selected_index + 1) % len(self.options)
            elif key == KEY_ESC:
                return "main_menu"
            elif key == KEY_ENTER:
                chosen_option = self.options[self.selected_index]
                if chosen_option == "Edit Characters":
                    return "character_editor" # New signal
                elif chosen_option == "Edit Cards":
                    return "card_editor" # New signal
                elif chosen_option == "Edit Adventures":
                    return "adventure_editor"
                elif chosen_option == "Edit Events":
                    return "event_editor"
                elif chosen_option == "Edit Relics":
                    return "relic_editor"
                elif chosen_option == "Edit Sandbox World":
                    return "world_editor"
                elif chosen_option == "Edit Sandbox Recipes":
                    return "recipe_editor"
                elif chosen_option == "Edit Sandbox Encounters":
                    return "encounter_editor"
                elif chosen_option == "Back to Main Menu":
                    return "main_menu"

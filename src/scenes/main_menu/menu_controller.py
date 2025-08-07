# src/scenes/main_menu/menu_controller.py
from .menu_view import MenuView
from ...keyboard import get_key, KEY_UP, KEY_DOWN, KEY_ENTER

class MainMenuController:
    """Handles logic for the animated main menu."""
    def __init__(self):
        self.options = ["Start Game", "Settings", "Card Editor", "Quit"]
        self.view = MenuView(self.options)
        self.selected_index = 0

    def run(self) -> str:
        """Runs the main menu loop and returns the next scene's name."""
        # This loop is designed around the blocking `get_key`.
        # The animation happens because we redraw after every key press.
        while True:
            self.view.display(self.selected_index)
            key = get_key()

            if key == KEY_UP:
                self.selected_index = (self.selected_index - 1) % len(self.options)
            elif key == KEY_DOWN:
                self.selected_index = (self.selected_index + 1) % len(self.options)
            elif key == KEY_ENTER:
                chosen_option = self.options[self.selected_index]
                # Return the signal for the AppController
                if chosen_option == "Start Game": return "start_game"
                if chosen_option == "Settings": return "settings"
                if chosen_option == "Card Editor": return "editor"
                if chosen_option == "Quit": return "quit"
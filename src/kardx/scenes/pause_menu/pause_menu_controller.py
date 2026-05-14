# src/scenes/pause_menu/pause_menu_controller.py
import os
from .pause_menu_view import PauseMenuView
from ...keyboard import get_key, KEY_UP, KEY_DOWN, KEY_ENTER, KEY_ESC

class PauseMenuController:
    """Handles the pause menu logic."""
    def __init__(self):
        self.options = ["Resume", "Quit to Menu"]
        self.view = PauseMenuView()
        self.selected_index = 0

    def run(self) -> str:
        """Returns 'resume' or 'main_menu'."""
        try:
            term_size = os.get_terminal_size()
            ### CORRECTED ATTRIBUTE NAME: rows -> lines ###
            term_width, term_height = term_size.columns, term_size.lines
        except OSError:
            term_width, term_height = 80, 18

        while True:
            self.view.display(self.options, self.selected_index, term_width, term_height)
            key = get_key()

            if key == KEY_UP:
                self.selected_index = (self.selected_index - 1) % len(self.options)
            elif key == KEY_DOWN:
                self.selected_index = (self.selected_index + 1) % len(self.options)
            elif key == KEY_ENTER:
                chosen = self.options[self.selected_index]
                if chosen == "Resume": return "resume"
                if chosen == "Quit to Menu": return "main_menu"
            elif key == KEY_ESC:
                return "resume"
# src/scenes/pause_menu/pause_menu_controller.py
from .pause_menu_view import PauseMenuView
from ...keyboard import get_key, KEY_UP, KEY_DOWN, KEY_ENTER, KEY_ESC
from ...view_utils import paused_terminal, terminal_size

class PauseMenuController:
    """Handles the pause menu logic."""
    def __init__(self):
        self.options = ["Resume", "Quit to Menu"]
        self.view = PauseMenuView()
        self.selected_index = 0

    def run(self) -> str:
        """Returns 'resume' or 'main_menu'."""
        with paused_terminal():
            return self._run_menu()

    def _run_menu(self) -> str:
        while True:
            term_width, term_height = terminal_size()
            self.view.display(self.options, self.selected_index, term_width, term_height)
            key = get_key()

            if isinstance(key, tuple) and key[0] == "pause":
                return "resume" if key[1] == 0 else "main_menu"
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

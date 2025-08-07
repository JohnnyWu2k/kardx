# src/scenes/character_select/character_select_controller.py
from pathlib import Path
from .character_select_view import CharacterSelectView
from ...loader import load_json5_data
from ...keyboard import get_key, KEY_UP, KEY_DOWN, KEY_ENTER, KEY_ESC

class CharacterSelectController:
    """Handles the logic for the character selection screen."""
    def __init__(self):
        self.characters = self._load_characters()
        self.view = CharacterSelectView(self.characters)
        self.selected_index = 0

    def _load_characters(self) -> list[dict]:
        """Loads playable characters from the data file."""
        char_data = load_json5_data(Path("data/characters.jsonc"))
        if not char_data: return []
        
        player_options = [
            {'id': k, 'name': v.get('display_name', k)}
            for k, v in char_data.items() if k.startswith("player_")
        ]
        return player_options

    def run(self) -> str | None:
        """
        Runs the character selection loop.
        Returns the chosen character ID string, or None if escaped.
        """
        if not self.characters:
            print("No playable characters found!")
            return None

        while True:
            self.view.display(self.selected_index)
            key = get_key()

            if key == KEY_UP:
                self.selected_index = (self.selected_index - 1) % len(self.characters)
            elif key == KEY_DOWN:
                self.selected_index = (self.selected_index + 1) % len(self.characters)
            elif key == KEY_ENTER:
                return self.characters[self.selected_index]['id']
            elif key == KEY_ESC:
                return None # Signal to go back
# src/scenes/character_select/character_select_view.py
import os
import re
from wcwidth import wcswidth
# Import from our new, centralized utility module
from ...view_utils import clear_screen, Colors, get_visible_len

class CharacterSelectView:
    """Displays the character selection screen."""
    def __init__(self, characters: list[dict]):
        self.characters = characters

    def _get_centered_line(self, text: str, width: int) -> str:
        """Helper function to center a line of text based on visible length."""
        padding = (width - get_visible_len(text)) // 2
        return ' ' * padding + text

    def display(self, selected_index: int):
        """Renders the character selection menu."""
        try:
            term_width = os.get_terminal_size().columns
        except OSError:
            term_width = 80
        
        clear_screen()
        
        box_width = 40
        
        # ... (Title and border drawing logic remains the same) ...
        print("\n" * 4)
        print(self._get_centered_line("┌" + "─" * box_width + "┐", term_width))
        print(self._get_centered_line("│" + " " * box_width + "│", term_width))
        title = "CHARACTER SELECT"
        print(self._get_centered_line(f"│{title:^{box_width}}│", term_width))
        print(self._get_centered_line("│" + " " * box_width + "│", term_width))
        print(self._get_centered_line("├" + "─" * box_width + "┤", term_width))
        print(self._get_centered_line("│" + " " * box_width + "│", term_width))

        ### MODIFIED: New selection style ###
        for i, char_info in enumerate(self.characters):
            option_text = char_info['name']
            
            if i == selected_index:
                # Selected item: indicator + one less space on the left
                line_content = f"> {option_text}"
                colored_content = Colors.accent(line_content)
            else:
                # Unselected item: two spaces on the left
                line_content = f"  {option_text}"
                colored_content = line_content

            # Universal centering logic
            padding = (box_width - get_visible_len(colored_content)) // 2
            padding_right = box_width - get_visible_len(colored_content) - padding
            line_str = f"│{' ' * padding}{colored_content}{' ' * padding_right}│"
            print(self._get_centered_line(line_str, term_width))

        print(self._get_centered_line("│" + " " * box_width + "│", term_width))
        print(self._get_centered_line("└" + "─" * box_width + "┘", term_width))
        
        footer_text = "Use UP/DOWN arrows, ENTER to confirm."
        print("\n")
        print(self._get_centered_line(footer_text, term_width))
# src/scenes/main_menu/menu_view.py
import os
import random
import re
from wcwidth import wcswidth
# Import from the new utility file
from ...view_utils import clear_screen, Colors, get_visible_len
from ...settings import settings_manager

class MenuView:
    """Displays a polished, centered, and animated main menu."""
    def __init__(self, options: list[str]):
        self.options = options
        self.title_parts = ["K", "A", "R", "D", "-", "X"]
        self.frame_count = 0 # frame_count can be kept for title animation

    def _get_centered_line(self, text: str, width: int) -> str:
        """Helper function to center a line of text based on visible length."""
        padding = (width - get_visible_len(text)) // 2
        return ' ' * padding + text

    def display(self, selected_index: int):
        try:
            term_width = os.get_terminal_size().columns
        except OSError:
            term_width = 80
        
        clear_screen()
        
        box_width = 38
        
        # ... (Title and border drawing logic remains the same) ...
        print("\n" * 4)
        print(self._get_centered_line("┌" + "─" * box_width + "┐", term_width))
        print(self._get_centered_line("│" + " " * box_width + "│", term_width))
        animated_title = ""
        for char in self.title_parts:
            if char != '-' and settings_manager.get("enable_menu_animations", True) and random.random() > 0.5:
                color_func = random.choice([Colors.negative, Colors.neutral, Colors.white])
                animated_title += color_func(char)
            else:
                animated_title += char
            animated_title += " "
        title_padding = (box_width - get_visible_len(animated_title)) // 2
        title_padding_right = box_width - get_visible_len(animated_title) - title_padding
        print(self._get_centered_line("│" + ' ' * title_padding + animated_title + ' ' * title_padding_right + "│", term_width))
        print(self._get_centered_line("│" + " " * box_width + "│", term_width))
        print(self._get_centered_line("├" + "─" * box_width + "┤", term_width))
        print(self._get_centered_line("│" + " " * box_width + "│", term_width))


        ### MODIFIED: New selection style ###
        for i, option in enumerate(self.options):
            if i == selected_index:
                # Selected item: indicator + one less space on the left
                line_content = f"> {option}"
                colored_content = Colors.accent(line_content)
            else:
                # Unselected item: two spaces on the left
                line_content = f"  {option}"
                colored_content = line_content # No color for unselected items

            # Universal centering logic for both selected and unselected
            padding = (box_width - get_visible_len(colored_content)) // 2
            padding_right = box_width - get_visible_len(colored_content) - padding
            line_str = f"│{' ' * padding}{colored_content}{' ' * padding_right}│"
            print(self._get_centered_line(line_str, term_width))
        
        print(self._get_centered_line("│" + " " * box_width + "│", term_width))
        print(self._get_centered_line("└" + "─" * box_width + "┘", term_width))
        
        footer_text = "Use UP/DOWN arrows, ENTER to confirm."
        print("\n")
        print(self._get_centered_line(footer_text, term_width))
        
        self.frame_count += 1
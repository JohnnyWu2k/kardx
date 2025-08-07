# src/scenes/editor/editor_menu_view.py
import os
from ...view_utils import clear_screen, Colors, get_visible_len

class EditorMenuView:
    """Displays the main menu for the editor."""

    def __init__(self, options: list[str]):
        self.options = options

    def _get_centered_line(self, text: str, width: int) -> str:
        padding = (width - get_visible_len(text)) // 2
        return ' ' * padding + text

    def display(self, selected_index: int):
        try:
            term_width = os.get_terminal_size().columns
        except OSError:
            term_width = 80
        
        clear_screen()
        
        box_width = 40
        
        print("\n" * 4)
        print(self._get_centered_line("┌" + "─" * box_width + "┐", term_width))
        
        title = "CONTENT EDITOR"
        print(self._get_centered_line(f"│{title:^{box_width}}│", term_width))
        
        print(self._get_centered_line("├" + "─" * box_width + "┤", term_width))
        print(self._get_centered_line("│" + " " * box_width + "│", term_width))

        for i, option in enumerate(self.options):
            if i == selected_index:
                line_content = f"> {option}"
                colored_content = Colors.accent(line_content)
            else:
                line_content = f"  {option}"
                colored_content = line_content

            padding = (box_width - get_visible_len(colored_content)) // 2
            padding_right = box_width - get_visible_len(colored_content) - padding
            line_str = f"│{' ' * padding}{colored_content}{' ' * padding_right}│"
            print(self._get_centered_line(line_str, term_width))
        
        print(self._get_centered_line("│" + " " * box_width + "│", term_width))
        print(self._get_centered_line("└" + "─" * box_width + "┘", term_width))
        
        footer_text = "Select content to edit (ESC to go back)."
        print("\n")
        print(self._get_centered_line(footer_text, term_width))
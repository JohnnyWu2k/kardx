# src/scenes/settings/settings_view.py
import os
from ...settings import settings_manager
# Import all the necessary tools from our new utility module
from ...view_utils import clear_screen, Colors, get_visible_len
from ...view_utils import clear_screen, Colors, get_visible_len # Use the new Colors


class SettingsView:
    """Displays the settings menu."""
    
    ### MODIFIED: Now uses the standard get_visible_len function ###
    def _get_centered_line(self, text: str, width: int) -> str:
        """Helper function to center a line of text based on visible length."""
        # Use the robust function instead of manual replacement
        padding = (width - get_visible_len(text)) // 2
        return ' ' * padding + text

    def display(self, options: list[dict], selected_index: int):
        try:
            term_width = os.get_terminal_size().columns
        except OSError:
            term_width = 80
        
        clear_screen()
        
        print("\n" * 4)
        print(self._get_centered_line("--- SETTINGS ---", term_width))
        print("\n" * 2)

        for i, option in enumerate(options):
            key = option['key']
            name = option['name']
            value = settings_manager.get(key)
            
            if isinstance(value, bool):
                display_value = Colors.positive("ON") if value else Colors.negative("OFF")
            elif isinstance(value, float):
                display_value = f"{value:.1f}x"
            else:
                display_value = str(value).upper()

            line = f"{name}: < {display_value} >"
            
            if i == selected_index:
                print(self._get_centered_line(Colors.accent(f"> {line} "), term_width))
            else:
                print(self._get_centered_line(f"  {line}", term_width))
        
        print("\n" * 3)
        print(self._get_centered_line("Use UP/DOWN to select, LEFT/RIGHT to change value.", term_width))
        print(self._get_centered_line("Press ESC to return to main menu.", term_width))
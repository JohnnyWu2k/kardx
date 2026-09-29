# src/scenes/pause_menu/pause_menu_view.py
from ...view_utils import Colors, get_visible_len, render_overlay

class PauseMenuView:
    """Displays a large, immersive pause menu panel."""

    def display(self, options: list[str], selected_index: int, term_width: int, term_height: int):
        """
        Draws a large pause menu that takes up a significant portion of the screen.
        """
        ### DESIGN TWEAKS for a larger panel ###
        # Let's make the box width a percentage of the terminal width
        box_width = min(term_width, max(20, int(term_width * 0.6)))
        # Ensure it's an even number for cleaner centering
        if box_width % 2 != 0:
            box_width -= 1
            
        # Height is determined by content + padding
        box_height = 5 + (len(options) * 2)
        
        start_col = (term_width - box_width) // 2
        start_row = max(0, (term_height - box_height) // 2)
            
        # --- Main Panel ---
        panel = []
        
        # Top border
        panel.append("┌" + "─" * (box_width - 2) + "┐")
        
        # Title
        title = " GAME PAUSED "
        panel.append(f"│{title:^{box_width - 2}}│")
        
        # Separator
        panel.append("├" + "─" * (box_width - 2) + "┤")
        
        # Options with vertical spacing
        for i, option in enumerate(options):
            panel.append("│" + " " * (box_width - 2) + "│") # Spacer line
            
            if i == selected_index:
                line_content = f"> {option} "
                colored_content = Colors.accent(line_content)
                padding = (box_width - 2 - get_visible_len(colored_content)) // 2
                padding_right = box_width - 2 - get_visible_len(colored_content) - padding
                line_str = f"│{' ' * padding}{colored_content}{' ' * padding_right}│"
            else:
                line_content = f"  {option}  "
                line_str = f"│{line_content:^{box_width - 2}}│"
            panel.append(line_str)
        
        # Bottom padding and border
        panel.append("│" + " " * (box_width - 2) + "│") # Spacer line
        panel.append("└" + "─" * (box_width - 2) + "┘")
        
        render_overlay(panel, start_col, start_row)

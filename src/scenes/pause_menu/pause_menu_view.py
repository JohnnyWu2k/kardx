# src/scenes/pause_menu/pause_menu_view.py
import sys
from ...view_utils import Colors, get_visible_len

class PauseMenuView:
    """Displays a large, immersive pause menu panel."""

    def display(self, options: list[str], selected_index: int, term_width: int, term_height: int):
        """
        Draws a large pause menu that takes up a significant portion of the screen.
        """
        ### DESIGN TWEAKS for a larger panel ###
        # Let's make the box width a percentage of the terminal width
        box_width = int(term_width * 0.6) # 60% of screen width
        # Ensure it's an even number for cleaner centering
        if box_width % 2 != 0:
            box_width -= 1
            
        # Height is determined by content + padding
        box_height = 4 + (len(options) * 2) # Title, separators, and spaced-out options
        
        start_col = (term_width - box_width) // 2
        start_row = (term_height - box_height) // 2
            
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
        
        # "Paste" the panel onto the screen
        for i, line in enumerate(panel):
            # Ensure we don't try to draw outside the screen boundaries
            if start_row + i < term_height:
                print(f"\033[{start_row + i};{start_col}H", end="")
                print(line, end="")

        # --- Final Touches ---
        sys.stdout.flush()
        print(f"\033[{term_height};0H", end="") # Hide cursor
        sys.stdout.flush()
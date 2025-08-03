# src/view.py
import os
from collections import deque
from wcwidth import wcswidth
from .player import Player
from .card import Card

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_display_width(text: str) -> int:
    return wcswidth(text)

class CLIView:
    """Handles all CLI rendering with a focus on a polished, seamless layout."""

    def _format_card(self, card: Card) -> list[str]:
        """
        Formats a card into a perfectly symmetrical, fixed-size ASCII art block.
        This version uses a robust padding calculation to ensure frame integrity.
        """
        card_width = 24
        total_height = 8
        lines = []

        # Mana cost visualization
        mana_symbol = '◆'
        cost_display = mana_symbol * card.cost
        
        # --- Header with precise padding logic ---
        lines.append(f"┌{'─' * (card_width - 2)}┐")
        
        # Title line calculation
        title = card.name
        
        # Define the available space for text *inside* the side borders "│ │"
        content_area_width = card_width - 4
        
        # Calculate widths of left and right elements
        title_width = get_display_width(title)
        cost_width = get_display_width(cost_display)
        
        # Calculate the exact number of spaces needed between them
        padding_width = content_area_width - title_width - cost_width
        
        # Defensive check to prevent negative padding
        padding = ' ' * max(0, padding_width)
        
        # Construct the perfectly balanced inner content
        inner_content = f"{title}{padding}{cost_display}"
        
        title_line = f"│ {inner_content} │"
        lines.append(title_line)
        
        lines.append(f"├{'─' * (card_width - 2)}┤")

        # --- Body ---
        desc_lines = []
        current_line = ""
        for word in card.description.split():
            if get_display_width(current_line + word + " ") > card_width - 4:
                desc_lines.append(current_line.strip())
                current_line = word + " "
            else:
                current_line += word + " "
        desc_lines.append(current_line.strip())

        for line in desc_lines:
            lines.append(f"│ {self.pad_str(line, card_width - 4)} │")
            
        # Padding for fixed height
        while len(lines) < total_height - 1:
            lines.append(f"│{' ' * (card_width - 2)}│")

        # --- Footer ---
        lines.append(f"└{'─' * (card_width - 2)}┘")
        return lines
    
    # Helper function from previous version, used in body formatting.
    def pad_str(self, text: str, width: int) -> str:
        padding_needed = width - get_display_width(text)
        return text + ' ' * max(0, padding_needed)

    def display_board(self, player: Player, enemy: Player, action_log: deque):
        clear_screen()
        
        print("=" * 80)
        print(f"ENEMY [ {enemy.name} ]")
        print(f"    HP: {enemy.hp}/{enemy.max_hp}  |  DEF: {enemy.block}")
        print("=" * 80)
        print("\n")

        print("--- Battle Log ---")
        if not action_log: print("> Awaiting action...")
        for message in action_log: print(f"> {message}")
        print("-" * 30)
        print("\n")

        print("--- Your Hand (Select a card to play) ---")
        if not player.hand:
            print("(Hand is empty)")
        else:
            card_art = [self._format_card(card) for card in player.hand]
            num_lines = len(card_art[0]) if card_art else 0
            for i in range(num_lines):
                print("  ".join(lines[i] for lines in card_art))
        print("\n")

        print("=" * 80)
        print(f"PLAYER [ {player.name} ]")
        print(f"    HP: {player.hp}/{player.max_hp}  |  Mana: {player.mana}/{player.max_mana}  |  DEF: {player.block}")
        print(f"    Deck: {len(player.deck)} cards  |  Discard: {len(player.discard_pile)} cards")
        print("=" * 80)

    def get_player_input(self, hand_size: int) -> str:
        prompt = f"Choose a card (1-{hand_size}) or type 'e' to end turn: "
        return input(prompt).strip().lower()
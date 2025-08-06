# src/view.py
import os
import time
from collections import deque
from wcwidth import wcswidth
from .player import Player
from .card import Card

# ANSI color codes for better feedback
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    WHITE = '\033[97m'
    ENDC = '\033[0m'

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_display_width(text: str) -> int:
    return wcswidth(text)

class CLIView:
    # ... _format_card, pad_str remain the same ...
    def _format_card(self, card: Card, is_selected: bool) -> list[str]:
        # ... no change ...
        top_left, top_right = ("╔", "╗") if is_selected else ("┌", "┐")
        bottom_left, bottom_right = ("╚", "╝") if is_selected else ("└", "┘")
        horz = "═" if is_selected else "─"
        vert = "║" if is_selected else "│"
        card_width, total_height = 24, 8
        lines = []
        mana_symbol = '◆'
        cost_display = mana_symbol * card.cost
        lines.append(f"{top_left}{horz * (card_width - 2)}{top_right}")
        title = card.name
        content_area_width = card_width - 4
        title_width, cost_width = get_display_width(title), get_display_width(cost_display)
        padding = ' ' * max(0, content_area_width - title_width - cost_width)
        inner_content = f"{title}{padding}{cost_display}"
        title_line = f"{vert} {inner_content} {vert}"
        lines.append(title_line)
        lines.append(f"{vert}{'─' * (card_width - 2)}{vert}")
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
            lines.append(f"{vert} {self.pad_str(line, card_width - 4)} {vert}")
        while len(lines) < total_height - 1:
            lines.append(f"{vert}{' ' * (card_width - 2)}{vert}")
        lines.append(f"{bottom_left}{horz * (card_width - 2)}{bottom_right}")
        return lines

    def pad_str(self, text: str, width: int) -> str:
        padding_needed = width - get_display_width(text)
        return text + ' ' * max(0, padding_needed)

    def display_board(self, player: Player, enemy: Player, action_log: deque, selected_index: int | None = None, animation_info: dict | None = None):
        clear_screen()
        # Enemy display
        print("="*80)
        enemy_line = f"ENEMY [ {enemy.name} ]"
        if animation_info and enemy == animation_info.get('target'):
             enemy_line += f"   {animation_info.get('text')}"
        print(enemy_line)
        print(f"    HP: {enemy.hp}/{enemy.max_hp}  |  DEF: {enemy.defend}  |  Mana: {enemy.mana}/{enemy.max_mana}")
        print("="*80); print("\n")
        
        # Log display...
        print("--- Battle Log ---");
        if not action_log: print("> Awaiting action...")
        for message in action_log: print(f"> {message}")
        print("-" * 30); print("\n")

        # Hand display...
        print("--- Your Hand (←/→ to select, Enter to play, 'e' to end turn, Esc to quit) ---")
        if not player.hand: print("(Hand is empty)")
        else:
            card_art = [self._format_card(card, i == selected_index) for i, card in enumerate(player.hand)]
            if card_art:
                num_lines = len(card_art[0])
                for i in range(num_lines): print("  ".join(lines[i] for lines in card_art))
        print("\n")

        # Player display
        print("="*80)
        player_line = f"PLAYER [ {player.name} ]"
        if animation_info and player == animation_info.get('target'):
            player_line += f"   {animation_info.get('text')}"
        print(player_line)
        print(f"    HP: {player.hp}/{player.max_hp}  |  Mana: {player.mana}/{player.max_mana}  |  DEF: {player.defend}")
        print(f"    Deck: {len(player.deck)} cards  |  Discard: {len(player.discard_pile)} cards")
        print("="*80)
    
    ### MODIFIED: More detailed animation logic ###
    def play_animation(self, player, enemy, action_log, events):
        """Plays a sequence of animations using more detailed event info."""
        for event in events:
            animation_steps = [] # An animation can have multiple steps (e.g., block then damage)
            
            if event['type'] == 'damage':
                # Step 1: Show block effect if any
                if event['blocked'] > 0:
                    text = f"{Colors.BLUE}🛡️ -{event['blocked']} DEF{Colors.ENDC}"
                    animation_steps.append({'target': event['target'], 'text': text, 'duration': 0.5})
                # Step 2: Show damage effect if any
                if event['value'] > 0:
                    text = f"{Colors.RED}💔 -{event['value']} HP{Colors.ENDC}"
                    animation_steps.append({'target': event['target'], 'text': text, 'duration': 0.5})

            elif event['type'] == 'defend':
                text = f"{Colors.BLUE}🛡️ +{event['value']} DEF{Colors.ENDC}"
                animation_steps.append({'target': event['target'], 'text': text, 'duration': 0.6})

            elif event['type'] == 'heal':
                text = f"{Colors.GREEN}💖 +{event['value']} HP{Colors.ENDC}"
                animation_steps.append({'target': event['target'], 'text': text, 'duration': 0.6})
            
            # Execute the animation steps
            for step in animation_steps:
                self.display_board(player, enemy, action_log, animation_info=step)
                time.sleep(step['duration'])

    def display_game_over(self, player: Player, enemy: Player):
        # ... (no change) ...
        print("\n" + "="*25)
        if player.hp <= 0: print("      YOU WERE DEFEATED")
        elif enemy.hp <= 0: print("      VICTORY!")
        else: print("      GAME OVER")
        print("="*25)
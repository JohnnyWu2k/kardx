# src/scenes/game/game_view.py
import time
from collections import deque
from wcwidth import wcswidth
from ...player import Player
from ...card import Card
from ...settings import settings_manager
# Import from the new utility file
from ...view_utils import clear_screen, Colors, get_visible_len

class GameView:
    # The Colors class is now removed from here
    # get_display_width is replaced by get_visible_len from view_utils
    # clear_screen is now imported from view_utils
    
    # ... The rest of the methods are the same, but now use Colors.red(), etc.
    # and we need to fix one small bug in play_animation
    def _format_card(self, card: Card, is_selected: bool) -> list[str]:
        #... (no change in logic, just relies on imported Colors)
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
        title_width, cost_width = get_visible_len(title), get_visible_len(cost_display)
        padding = ' ' * max(0, content_area_width - title_width - cost_width)
        inner_content = f"{title}{padding}{cost_display}"
        title_line = f"{vert} {inner_content} {vert}"
        lines.append(title_line)
        lines.append(f"{vert}{'─' * (card_width - 2)}{vert}")
        desc_lines = []
        current_line = ""
        for word in card.description.split():
            if get_visible_len(current_line + word + " ") > card_width - 4:
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

    def _format_enemy_card(self, card: Card, is_being_played: bool) -> str:
        if is_being_played:
            return Colors.positive(f" >[{card.name}]< ")
        return f" [{card.name}] "

    def pad_str(self, text: str, width: int) -> str:
        padding_needed = width - get_visible_len(text)
        return text + ' ' * max(0, padding_needed)
    
    def display_board(self, player: Player, enemy: Player, action_log: deque,
                      selected_index: int | None = None,
                      animation_info: dict | None = None,
                      enemy_card_played_index: int | None = None):
        clear_screen()

        # --- DEBUG BLOCK ---
        show_setting = settings_manager.get("show_enemy_hand")
        is_hand_not_empty = bool(enemy.hand) # Explicitly check if the list is not empty
        print(f"--- DEBUG INFO ---")
        print(f"Setting 'show_enemy_hand': {show_setting} (Type: {type(show_setting)})")
        print(f"Enemy hand object: {enemy.hand}")
        print(f"Enemy hand is not empty: {is_hand_not_empty}")
        print(f"Combined condition (setting AND hand): {show_setting and is_hand_not_empty}")
        print(f"--------------------")
        # --- END DEBUG BLOCK ---

        print("="*80)
        enemy_line = f"ENEMY [ {enemy.name} ]"
        if animation_info and enemy == animation_info.get('target'):
             enemy_line += f"   {animation_info.get('text')}"
        print(enemy_line)
        print(f"    HP: {enemy.hp}/{enemy.max_hp}  |  DEF: {enemy.defend}  |  Mana: {enemy.mana}/{enemy.max_mana}")

        if settings_manager.get("show_enemy_hand") and enemy.hand:
            enemy_hand_str = "".join(
                self._format_enemy_card(card, i == enemy_card_played_index)
                for i, card in enumerate(enemy.hand)
            )
            print(f"    Hand: {enemy_hand_str}")

        print("="*80); print("\n")
        print("--- Battle Log ---");
        if not action_log: print("> Awaiting action...")
        for message in action_log: print(f"> {message}")
        print("-" * 30); print("\n")
        print("--- Your Hand (←/→ to select, Enter to play, 'e' to end turn, Esc to quit) ---")
        if not player.hand: print("(Hand is empty)")
        else:
            card_art = [self._format_card(card, i == selected_index) for i, card in enumerate(player.hand)]
            if card_art:
                num_lines = len(card_art[0])
                for i in range(num_lines): print("  ".join(lines[i] for lines in card_art))
        print("\n")
        print("="*80)
        player_line = f"PLAYER [ {player.name} ]"
        if animation_info and player == animation_info.get('target'):
            player_line += f"   {animation_info.get('text')}"
        print(player_line)
        print(f"    HP: {player.hp}/{player.max_hp}  |  Mana: {player.mana}/{player.max_mana}  |  DEF: {player.defend}")
        print(f"    Deck: {len(player.deck)} cards  |  Discard: {len(player.discard_pile)} cards")
        print("="*80)

    ### BUG FIX in play_animation ###
    def play_animation(self, player, enemy, action_log, events):
        speed_mult = settings_manager.get("animation_speed_multiplier", 1.0)
        for event in events:
            animation_steps = []
            if event['type'] == 'damage':
                if event['blocked'] > 0:
                    text = Colors.neutral(f"🛡️ -{event['blocked']} DEF")
                    animation_steps.append({'target': event['target'], 'text': text, 'duration': 0.5})
                if event['value'] > 0:
                    text = Colors.negative(f"💔 -{event['value']} HP")
                    animation_steps.append({'target': event['target'], 'text': text, 'duration': 0.5})
            elif event['type'] == 'defend':
                text = Colors.neutral(f"🛡️ +{event['value']} DEF")
                animation_steps.append({'target': event['target'], 'text': text, 'duration': 0.6})
            elif event['type'] == 'heal':
                text = Colors.positive(f"💖 +{event['value']} HP")
                animation_steps.append({'target': event['target'], 'text': text, 'duration': 0.6})
            elif event['type'] == 'mana_gain':
                text = Colors.accent(f"💧 +{event['value']} Mana")
                animation_steps.append({'target': event['target'], 'text': text, 'duration': 0.6})

            elif event['type'] == 'max_mana_gain':
                text = Colors.accent(f"💧 Max Mana +{event['value']}!")
                animation_steps.append({'target': event['target'], 'text': text, 'duration': 0.7})
            
            for step in animation_steps:
                self.display_board(player, enemy, action_log, animation_info=step)
                # The sleep was outside the loop, causing only the last step's duration to be used.
                time.sleep(step['duration'] * speed_mult)

    def display_game_over(self, player: Player, enemy: Player):
        print("\n" + "="*25)
        if player.hp <= 0: print(Colors.negative("    YOU WERE DEFEATED"))
        elif enemy.hp <= 0: print(Colors.positive("      VICTORY!"))
        else: print("      GAME OVER")
        print("="*25)
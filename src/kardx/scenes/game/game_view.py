import textwrap
import time
from collections.abc import Callable
from collections import deque

from ...card import Card
from ...player import Player
from ...settings import settings_manager
from ...view_utils import Colors, get_visible_len, render_screen, terminal_size


class GameView:
    MIN_CARD_WIDTH = 14
    MAX_CARD_WIDTH = 28
    CARD_GAP = 2

    def _clip_text(self, text: str, width: int) -> str:
        if width <= 0:
            return ""
        if get_visible_len(text) <= width:
            return text
        if width <= 1:
            return text[:width]
        return text[:width - 1] + "~"

    def _pad_str(self, text: str, width: int) -> str:
        return text + " " * max(0, width - get_visible_len(text))

    def _fit_line(self, text: str, width: int) -> str:
        return self._pad_str(self._clip_text(text, width), width)

    def _divider(self, width: int, char: str = "=") -> str:
        return char * width

    def _format_card(self, card: Card, is_selected: bool, card_width: int, card_height: int) -> list[str]:
        border_char = "=" if is_selected else "-"
        top = "+" + border_char * (card_width - 2) + "+"
        bottom = "+" + border_char * (card_width - 2) + "+"
        inner_width = card_width - 4
        mana = "*" * card.cost

        title_space = max(1, inner_width - len(mana) - 1)
        title = self._clip_text(card.name, title_space)
        title_line = title + " " * max(1, inner_width - get_visible_len(title) - len(mana)) + mana

        desc_height = max(1, card_height - 3)
        wrapped = textwrap.wrap(card.description, width=max(8, inner_width))[:desc_height]
        while len(wrapped) < desc_height:
            wrapped.append("")

        lines = [top, f"| {self._pad_str(title_line, inner_width)} |"]
        for desc in wrapped:
            lines.append(f"| {self._pad_str(desc, inner_width)} |")
        lines.append(bottom)
        return lines[:card_height]

    def _hand_layout(self, card_count: int, width: int) -> tuple[int, int]:
        if card_count <= 0:
            return 0, self.MIN_CARD_WIDTH

        full_row_width = width - self.CARD_GAP * (card_count - 1)
        if full_row_width >= self.MIN_CARD_WIDTH * card_count:
            card_width = full_row_width // card_count
            return card_count, min(self.MAX_CARD_WIDTH, max(self.MIN_CARD_WIDTH, card_width))

        columns = max(1, (width + self.CARD_GAP) // (self.MIN_CARD_WIDTH + self.CARD_GAP))
        columns = min(columns, card_count)
        card_width = (width - self.CARD_GAP * (columns - 1)) // columns
        return columns, max(self.MIN_CARD_WIDTH, min(self.MAX_CARD_WIDTH, card_width))

    def _format_hand(self, player: Player, selected_index: int | None, width: int, max_lines: int) -> list[str]:
        if not player.hand:
            return [self._fit_line("(Hand is empty)", width)]
        if max_lines < 5:
            names = "  ".join(
                (f"[{card.name}]" if i == selected_index else card.name)
                for i, card in enumerate(player.hand)
            )
            return [self._fit_line(names, width)]

        columns, card_width = self._hand_layout(len(player.hand), width)
        card_height = 8 if max_lines >= 8 else max(5, max_lines)
        rows: list[str] = []

        for start in range(0, len(player.hand), columns):
            chunk = player.hand[start:start + columns]
            rendered_cards = [
                self._format_card(card, start + idx == selected_index, card_width, card_height)
                for idx, card in enumerate(chunk)
            ]
            for line_index in range(card_height):
                line = (" " * self.CARD_GAP).join(card[line_index] for card in rendered_cards)
                rows.append(self._fit_line(line, width))
            if len(rows) >= max_lines:
                break
            if start + columns < len(player.hand):
                rows.append("")

        return rows[:max_lines]

    def _format_enemy_hand(self, enemy: Player, played_index: int | None, width: int) -> list[str]:
        if not settings_manager.get("show_enemy_hand") or not enemy.hand:
            return []

        parts = [
            Colors.positive(f">[{card.name}]<") if i == played_index else f"[{card.name}]"
            for i, card in enumerate(enemy.hand)
        ]
        raw = "Hand: " + " ".join(parts)
        wrapped = textwrap.wrap(raw, width=max(20, width - 4))
        return [self._fit_line("    " + line, width) for line in wrapped[:2]]

    def display_board(self, player: Player, enemy: Player, action_log: deque,
                      selected_index: int | None = None,
                      animation_info: dict | None = None,
                      enemy_card_played_index: int | None = None):
        width, height = terminal_size()
        log_limit = 5 if height >= 28 else 3 if height >= 22 else 1

        enemy_line = f"ENEMY [ {enemy.name} ]"
        if animation_info and enemy == animation_info.get('target'):
            enemy_line += f"   {animation_info.get('text')}"

        player_line = f"PLAYER [ {player.name} ]"
        if animation_info and player == animation_info.get('target'):
            player_line += f"   {animation_info.get('text')}"

        top_lines = [
            self._divider(width),
            self._fit_line(enemy_line, width),
            self._fit_line(
                f"    HP: {enemy.hp}/{enemy.max_hp}  |  DEF: {enemy.defend}  |  Mana: {enemy.mana}/{enemy.max_mana}",
                width,
            ),
            *self._format_enemy_hand(enemy, enemy_card_played_index, width),
            self._divider(width),
            "",
            self._fit_line("--- Battle Log ---", width),
        ]

        visible_log = list(action_log)[-log_limit:]
        if visible_log:
            top_lines.extend(self._fit_line(f"> {message}", width) for message in visible_log)
        else:
            top_lines.append(self._fit_line("> Awaiting action...", width))

        top_lines.extend([
            self._divider(min(width, 30), "-"),
            "",
            self._fit_line("--- Your Hand (<-/-> select, Enter play, q discard, e end, Esc pause) ---", width),
        ])

        bottom_lines = [
            self._divider(width),
            self._fit_line(player_line, width),
            self._fit_line(
                f"    HP: {player.hp}/{player.max_hp}  |  Mana: {player.mana}/{player.max_mana}  |  DEF: {player.defend}",
                width,
            ),
            self._fit_line(f"    Deck: {len(player.deck)} cards  |  Discard: {len(player.discard_pile)} cards", width),
            self._divider(width),
        ]

        available_hand_lines = max(1, height - len(top_lines) - len(bottom_lines))
        hand_lines = self._format_hand(player, selected_index, width, available_hand_lines)
        render_screen(top_lines + hand_lines + bottom_lines)

    def _animation_steps(self, events: list[dict]) -> list[dict]:
        steps = []
        for event in events:
            if event['type'] == 'damage':
                if event['blocked'] > 0:
                    text = Colors.neutral(f"-{event['blocked']} DEF")
                    steps.append({'target': event['target'], 'text': text, 'duration': 0.5})
                if event['value'] > 0:
                    text = Colors.negative(f"-{event['value']} HP")
                    steps.append({'target': event['target'], 'text': text, 'duration': 0.5})
            elif event['type'] == 'defend':
                text = Colors.neutral(f"+{event['value']} DEF")
                steps.append({'target': event['target'], 'text': text, 'duration': 0.6})
            elif event['type'] == 'heal':
                text = Colors.positive(f"+{event['value']} HP")
                steps.append({'target': event['target'], 'text': text, 'duration': 0.6})
            elif event['type'] == 'mana_gain':
                text = Colors.accent(f"+{event['value']} Mana")
                steps.append({'target': event['target'], 'text': text, 'duration': 0.6})
            elif event['type'] == 'max_mana_gain':
                text = Colors.accent(f"Max Mana +{event['value']}!")
                steps.append({'target': event['target'], 'text': text, 'duration': 0.7})
        return steps

    def play_animation(
        self,
        player,
        enemy,
        action_log,
        events,
        selected_index: int | None = None,
        on_tick: Callable[[int | None], int | None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> int | None:
        speed_mult = settings_manager.get("animation_speed_multiplier", 1.0)
        for step in self._animation_steps(events):
            if should_stop and should_stop():
                break
            if not on_tick:
                self.display_board(player, enemy, action_log, animation_info=step)
                time.sleep(step['duration'] * speed_mult)
                continue
            deadline = time.monotonic() + step['duration'] * speed_mult
            while True:
                if should_stop and should_stop():
                    return selected_index
                selected_index = on_tick(selected_index)
                if should_stop and should_stop():
                    return selected_index
                self.display_board(
                    player,
                    enemy,
                    action_log,
                    selected_index=selected_index,
                    animation_info=step,
                )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(0.05, remaining))
        return selected_index

    def display_game_over(self, player: Player, enemy: Player):
        lines = ["", "=" * 25]
        if player.hp <= 0:
            lines.append(Colors.negative("    YOU WERE DEFEATED"))
        elif enemy.hp <= 0:
            lines.append(Colors.positive("      VICTORY!"))
        else:
            lines.append("      GAME OVER")
        lines.append("=" * 25)
        render_screen(lines)

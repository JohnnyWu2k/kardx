import textwrap
import time
from collections.abc import Callable
from collections import deque

from ...card import Card
from ...player import Player
from ...settings import settings_manager
from ...view_utils import Colors, fit_to_width, get_visible_len, render_screen, terminal_size, set_mouse_targets


class GameView:
    MIN_CARD_WIDTH = 14
    MAX_CARD_WIDTH = 32
    CARD_GAP = 2

    def _clip_text(self, text: str, width: int) -> str:
        if width <= 0:
            return ""
        if get_visible_len(text) <= width:
            return text
        if width <= 1:
            return fit_to_width(text, width)
        return fit_to_width(text, width - 1) + "~"

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

        art = self._card_art(card, inner_width, max(3, card_height - 6)) if card_height >= 7 else []
        desc_height = max(0, card_height - 3 - len(art))
        wrapped = textwrap.wrap(card.description, width=max(8, inner_width))[:desc_height]
        while len(wrapped) < desc_height:
            wrapped.append("")

        lines = [top, f"| {self._pad_str(title_line, inner_width)} |"]
        for desc in art + wrapped:
            lines.append(f"| {self._fit_line(desc, inner_width)} |")
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
            index = max(0, selected_index or 0)
            names = f"{index + 1}/{len(player.hand)} [{player.hand[index].name}] (wheel to select)"
            return [self._fit_line(names, width)]

        columns, card_width = self._hand_layout(len(player.hand), width)
        card_height = min(16, max_lines) if max_lines >= 8 else max(5, max_lines)
        rows: list[str] = []
        visible_rows = max(1, (max_lines + 1) // (card_height + 1))
        selected_row = max(0, selected_index or 0) // columns
        first_row = max(0, selected_row - visible_rows + 1)

        for start in range(first_row * columns, len(player.hand), columns):
            chunk = player.hand[start:start + columns]
            rendered_cards = [
                self._format_card(card, start + idx == selected_index, card_width, card_height)
                for idx, card in enumerate(chunk)
            ]
            for line_index in range(card_height):
                line = (" " * self.CARD_GAP).join(card[line_index] for card in rendered_cards)
                rows.append(self._fit_line(" " * max(0, (width - get_visible_len(line)) // 2) + line, width))
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

    def _card_art(self, card, width=10, rows=3):
        # Native terminal pixel art remains crisp at every font size.
        text = (card.id + " " + card.name).lower()
        kind = next((key for key in ("fire", "ice", "heal", "defend", "mana") if key in text), None)
        if kind is None:
            effects = {effect.get("action") for effect in card.effects}
            healing = any(effect.get("action") == "add_hp" and effect.get("target") == "self"
                          and effect.get("value", 0) > 0 for effect in card.effects)
            kind = "heal" if healing else "defend" if "add_def" in effects else "mana" if effects & {"add_mana", "add_max_mana"} else "attack"
        from ttx.art import card_pixels
        return list(card_pixels(kind, width, rows))

    def _portrait(self, actor, enemy=False):
        name = actor.name.lower()
        if "rat" in name:
            pixels = ("     ▄▄ ▄▄  ", " ▄██████▄▀█ ", "▀▀  ▀█ ▀█   ")
        elif "wolf" in name:
            pixels = (" ▄       ▄▄ ", " ▀████████▀ ", "  ██  ██    ")
        elif any(word in name for word in ("warden", "guardian", "automaton", "sentry")):
            pixels = ("  ▄████▄  ", "██████████", "  ██  ██  ")
        elif "leech" in name:
            pixels = ("   ▄▄▄▄   ", " ▄██▀▀██▄ ", "  ▀████▀  ")
        else:
            pixels = ("  ▄██▄  ", "▄██████▄", " ██  ██ ")
        color = Colors.negative if enemy else Colors.accent
        return [color(row) for row in pixels]

    def _vital_lines(self, actor, width):
        now = time.monotonic()
        if not hasattr(self, "_vitals"):
            self._vitals = {}
        values = (actor.hp, actor.mana, actor.defend)
        previous, deltas, until = self._vitals.get(id(actor), (values, (0, 0, 0), 0))
        if values != previous:
            deltas = tuple(new - old for new, old in zip(values, previous))
            until = now + 1.8
        self._vitals[id(actor)] = values, deltas, until
        def metric(label, value, maximum, index, color):
            delta = deltas[index] if now < until else 0
            suffix = f"  {delta:+d}" if delta else ""
            bar_width = max(0, min(16, width - 25))
            filled = round(bar_width * max(0, min(1, value / max(1, maximum))))
            bar = " [" + "#" * filled + "-" * (bar_width - filled) + "]" if bar_width else ""
            text = f"{label} {value}/{maximum}" + bar + suffix
            return ("\033[1;7m" if delta else "\033[1m") + color(text) + "\033[0m"
        return [metric("HP", actor.hp, actor.max_hp, 0, Colors.positive),
                metric("MANA", actor.mana, actor.max_mana, 1, Colors.neutral) + f"  DEF {actor.defend}" +
                (f" ({deltas[2]:+d})" if now < until and deltas[2] else "")]

    def _fighter_panel(self, actor, label, width, animation_info, enemy=False):
        def center(text):
            return self._fit_line(" " * max(0, (width - get_visible_len(text)) // 2) + text, width)
        lines = [center(label + "  " + actor.name)]
        lines.extend(center(line) for line in self._vital_lines(actor, width))
        lines.append("")
        lines.extend(center(line) for line in self._portrait(actor, enemy))
        event = animation_info.get("text", "") if animation_info and animation_info.get("target") is actor else ""
        lines.append(center(event))
        return [self._fit_line(line, width) for line in lines]

    def display_board(self, player: Player, enemy: Player, action_log: deque,
                      selected_index: int | None = None,
                      animation_info: dict | None = None,
                      enemy_card_played_index: int | None = None):
        width, height = terminal_size()
        width, height = max(1, width), max(1, height)
        targets = []
        def centered(text):
            return self._fit_line(" " * max(0, (width - get_visible_len(text)) // 2) + text, width)
        def status(actor, label):
            text = f"{label} {actor.name}  HP {actor.hp}/{actor.max_hp}  DEF {actor.defend}  Mana {actor.mana}/{actor.max_mana}"
            if animation_info and actor == animation_info.get("target"):
                text += " " + animation_info.get("text", "")
            return centered(text)

        lines = [centered("KARD-X  /  BATTLE")]
        if width >= 90:
            panel_width = min(64, (width - 10) // 2)
            arena_width = panel_width * 2 + 6
            inset = max(0, (width - arena_width) // 2)
            lines.extend([""] * max(0, min(round(height * 0.10), height - 25)))
            left_panel = self._fighter_panel(player, "PLAYER", panel_width, animation_info)
            right_panel = self._fighter_panel(enemy, "ENEMY", panel_width, animation_info, True)
            for left, right in zip(left_panel, right_panel):
                lines.append(" " * inset + left + " " * 6 + right)
            names = " ".join(f"[{card.name}]" if settings_manager.get("show_enemy_hand") else "[?]" for card in enemy.hand)
            lines.append(" " * (inset + panel_width + 6) + self._fit_line(names, panel_width))
        else:
            # A compact vertical arena leaves at least seven rows for cards.
            for actor, label in ((enemy, "ENEMY"), (player, "PLAYER")):
                lines.append(centered(label + "  " + actor.name))
                vitals = self._vital_lines(actor, max(10, width - 2))
                lines.extend(centered(line) for line in vitals)
        details = f"Deck {len(player.deck)} / Discard {len(player.discard_pile)} | Enemy cards {len(enemy.hand)}"
        lines.append(centered(details))
        if action_log:
            lines.append(centered(str(action_log[-1])))
        # Reserve the lower central area for the hand, even on a tall screen.
        target_top = max(len(lines), min(round(height * 0.57), height - 10))
        lines.extend([""] * max(0, target_top - len(lines)))
        lines.append(centered("YOUR HAND / click select / wheel / arrows"))
        hand_top = len(lines)
        available = max(1, height - hand_top - 2)
        hand_lines = self._format_hand(player, selected_index, width, available)
        lines += hand_lines
        if player.hand and selected_index is not None and selected_index >= 0:
            card = player.hand[selected_index]
            lines.append(centered(f"{card.name}: {card.description}"))
        if player.hand:
            columns, card_width = self._hand_layout(len(player.hand), width)
            if available >= 5:
                card_height = min(16, available) if available >= 8 else max(5, available)
                visible_rows = max(1, (available + 1) // (card_height + 1))
                first_row = max(0, max(0, selected_index or 0) // columns - visible_rows + 1)
                for index in range(first_row * columns, len(player.hand)):
                    row, col = divmod(index - first_row * columns, columns)
                    row_count = min(columns, len(player.hand) - (first_row + row) * columns)
                    row_width = row_count * card_width + (row_count - 1) * self.CARD_GAP
                    top = hand_top + row * (card_height + 1)
                    left = max(0, (width - row_width) // 2) + col * (card_width + self.CARD_GAP)
                    if top >= hand_top + len(hand_lines):
                        break
                    targets.append((left, top, min(width, left + card_width), min(top + card_height, hand_top + len(hand_lines)), ("card", index)))
            elif selected_index is not None and selected_index >= 0:
                targets.append((0, hand_top, width, hand_top + 1, ("card", selected_index)))
        buttons = [("[Play]", b'<ENTER>'), ("[Discard]", b'q'), ("[End turn]", b'e'), ("[Pause]", b'<ESC>')]
        # Compact controls fit narrow terminals.
        if width < 40:
            buttons = [("[Play]", b'<ENTER>'), ("[End]", b'e'), ("[Pause]", b'<ESC>')]
        footer = " ".join(label for label, _ in buttons)
        top = min(height - 1, len(lines))
        left = max(0, (width - len(footer)) // 2)
        lines = lines[:top] + [centered(footer)]
        for label, action in buttons:
            targets.append((left, top, min(width, left + len(label)), top + 1, action))
            left += len(label) + 1
        render_screen(lines)
        set_mouse_targets(targets)

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
        set_mouse_targets([])
        lines = ["", "=" * 25]
        if player.hp <= 0:
            lines.append(Colors.negative("    YOU WERE DEFEATED"))
        elif enemy.hp <= 0:
            lines.append(Colors.positive("      VICTORY!"))
        else:
            lines.append("      GAME OVER")
        lines.append("=" * 25)
        render_screen(lines)

import textwrap

from ...adventure import AdventureData, AdventureNode, AdventureState
from ...view_utils import Colors, get_visible_len, render_screen, terminal_size


class AdventureView:
    def __init__(self, data: AdventureData):
        self.data = data

    def _center(self, text: str, width: int) -> str:
        padding = max(0, (width - get_visible_len(text)) // 2)
        return " " * padding + text

    def _fit(self, text: str, width: int) -> str:
        visible = get_visible_len(text)
        return text + " " * max(0, width - visible)

    def _wrap(self, text: str, width: int) -> list[str]:
        return textwrap.wrap(text, width=max(20, width)) or [""]

    def _status_lines(self, state: AdventureState, width: int) -> list[str]:
        relics = ", ".join(self.data.relic_name(relic_id) for relic_id in state.relic_ids) or "None"
        return [
            "=" * width,
            self._fit(f"{state.name} | {state.player_name}", width),
            self._fit(
                f"HP: {state.current_hp}/{state.max_hp}  Gold: {state.gold}  "
                f"Deck: {len(state.deck_ids)} cards  Relics: {relics}",
                width,
            ),
            "=" * width,
        ]

    def display_map(self, state: AdventureState, selected_index: int):
        width, _ = terminal_size()
        lines = self._status_lines(state, width)
        if state.visited_nodes:
            lines.extend(["", "Route:"])
            route = " -> ".join(f"{node.label} [{node.type}]" for node in state.visited_nodes)
            for line in self._wrap(route, width):
                lines.append(self._fit("  " + line, width))

        lines.extend(["", "Current routes:"])
        for index, node in enumerate(state.current_nodes):
            option_lines = self._format_node_option(node, index == selected_index, width)
            lines.extend(option_lines)

        lines.extend(["", "Use arrows, ENTER to travel, ESC for main menu."])
        render_screen(lines)

    def display_options(
        self,
        title: str,
        body: str,
        options: list[str],
        selected_index: int,
        state: AdventureState | None = None,
    ):
        width, _ = terminal_size()
        lines = self._status_lines(state, width) if state else ["=" * width]
        lines.extend(["", Colors.accent(title), ""])
        for paragraph in body.split("\n"):
            lines.extend(self._wrap(paragraph, width))
        lines.append("")
        for index, option in enumerate(options):
            prefix = "> " if index == selected_index else "  "
            line = prefix + option
            lines.append(Colors.accent(line) if index == selected_index else line)
        lines.extend(["", "Use arrows, ENTER to confirm, ESC to go back when available."])
        render_screen(lines)

    def display_message(self, title: str, messages: list[str], state: AdventureState | None = None):
        width, _ = terminal_size()
        lines = self._status_lines(state, width) if state else ["=" * width]
        lines.extend(["", Colors.accent(title), ""])
        for message in messages:
            lines.extend(self._wrap(message, width))
        lines.extend(["", "Press any key to continue."])
        render_screen(lines)

    def describe_node(self, node: AdventureNode) -> str:
        if node.type in {"Battle", "Elite", "Boss"}:
            reward = f"{node.gold} Gold"
            if node.relic:
                reward += " and a relic"
            enemy = self.data.characters.get(node.enemy or "", {})
            enemy_name = enemy.get("display_name", node.enemy or "Unknown")
            return f"Fight {enemy_name}. Reward: {reward}."
        if node.type == "Event":
            return "Choice event."
        if node.type == "Shop":
            return "Buy cards, thin deck, or buy relics."
        if node.type == "Rest":
            return "Heal or train one basic card."
        return node.label

    def _format_node_option(self, node: AdventureNode, selected: bool, width: int) -> list[str]:
        prefix = "> " if selected else "  "
        title = f"{prefix}{node.label:<16} {node.type:<6}"
        detail = self._node_detail(node)
        line = self._fit(f"{title}  {detail}", width)
        if get_visible_len(line) <= width:
            return [Colors.accent(line) if selected else line]

        lines = [
            self._fit(title, width),
            self._fit(" " * len(prefix) + "  " + detail, width),
        ]
        return [Colors.accent(item) if selected else item for item in lines]

    def _node_detail(self, node: AdventureNode) -> str:
        if node.type in {"Battle", "Elite", "Boss"}:
            enemy = self.data.characters.get(node.enemy or "", {})
            enemy_name = enemy.get("display_name", node.enemy or "Unknown")
            hp = enemy.get("hp", "?")
            mana = enemy.get("mana", "?")
            reward = f"{node.gold} Gold"
            if node.relic:
                reward += " + Relic"
            return f"Enemy: {enemy_name}  HP {hp}  Mana {mana}  Reward: {reward}"
        if node.type == "Event":
            event = self.data.events.get(node.event or "", {})
            title = event.get("title", node.label)
            return f"Event: {title}  Reward: choice"
        if node.type == "Shop":
            return "Spend Gold: buy cards / thin deck / relic"
        if node.type == "Rest":
            return "Recover HP or train a basic card"
        return self.describe_node(node)

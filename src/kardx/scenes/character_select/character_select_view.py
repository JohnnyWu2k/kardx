from ...view_utils import Colors, get_visible_len, render_screen, terminal_size


class CharacterSelectView:
    """Displays the character selection screen."""

    def __init__(self, characters: list[dict]):
        self.characters = characters

    def _center(self, text: str, width: int) -> str:
        padding = max(0, (width - get_visible_len(text)) // 2)
        return " " * padding + text

    def _box_line(self, content: str, box_width: int) -> str:
        padding = max(0, box_width - get_visible_len(content))
        left = padding // 2
        right = padding - left
        return "|" + " " * left + content + " " * right + "|"

    def display(self, selected_index: int):
        term_width, term_height = terminal_size()
        box_width = min(42, max(30, term_width - 4))
        top_pad = max(1, min(4, (term_height - len(self.characters) - 9) // 2))

        lines = [""] * top_pad
        lines.append(self._center("+" + "-" * box_width + "+", term_width))
        lines.append(self._center(self._box_line("", box_width), term_width))
        lines.append(self._center(self._box_line("CHARACTER SELECT", box_width), term_width))
        lines.append(self._center(self._box_line("", box_width), term_width))
        lines.append(self._center("+" + "-" * box_width + "+", term_width))

        for i, char_info in enumerate(self.characters):
            option_text = char_info["name"]
            content = Colors.accent(f"> {option_text}") if i == selected_index else f"  {option_text}"
            lines.append(self._center(self._box_line(content, box_width), term_width))

        lines.append(self._center("+" + "-" * box_width + "+", term_width))
        lines.append("")
        lines.append(self._center("Use UP/DOWN arrows, ENTER to confirm.", term_width))
        render_screen(lines)

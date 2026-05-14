from ...view_utils import Colors, get_visible_len, render_screen, terminal_size


class MenuView:
    """Displays the main menu."""

    def __init__(self, options: list[str]):
        self.options = options
        self.title_parts = ["K", "A", "R", "D", "-", "X"]
        self.frame_count = 0

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
        box_width = min(40, max(28, term_width - 4))

        title = Colors.accent(" ".join(self.title_parts))

        lines = []
        top_pad = max(1, min(4, (term_height - len(self.options) - 9) // 2))
        lines.extend([""] * top_pad)
        lines.append(self._center("+" + "-" * box_width + "+", term_width))
        lines.append(self._center(self._box_line("", box_width), term_width))
        lines.append(self._center(self._box_line(title, box_width), term_width))
        lines.append(self._center(self._box_line("", box_width), term_width))
        lines.append(self._center("+" + "-" * box_width + "+", term_width))

        for i, option in enumerate(self.options):
            content = Colors.accent(f"> {option}") if i == selected_index else f"  {option}"
            lines.append(self._center(self._box_line(content, box_width), term_width))

        lines.append(self._center("+" + "-" * box_width + "+", term_width))
        lines.append("")
        lines.append(self._center("Use UP/DOWN arrows, ENTER to confirm.", term_width))
        render_screen(lines)

        self.frame_count += 1

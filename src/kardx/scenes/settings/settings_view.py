from ...settings import settings_manager
from ...view_utils import Colors, get_visible_len, render_screen, terminal_size


class SettingsView:
    """Displays the settings menu."""

    def _center(self, text: str, width: int) -> str:
        padding = max(0, (width - get_visible_len(text)) // 2)
        return " " * padding + text

    def display(self, options: list[dict], selected_index: int):
        term_width, term_height = terminal_size()
        top_pad = max(1, min(4, (term_height - len(options) - 7) // 2))

        lines = [""] * top_pad
        lines.append(self._center("--- SETTINGS ---", term_width))
        lines.append("")

        for i, option in enumerate(options):
            key = option["key"]
            name = option["name"]
            value = settings_manager.get(key)

            if isinstance(value, bool):
                display_value = Colors.positive("ON") if value else Colors.negative("OFF")
            elif isinstance(value, float):
                display_value = f"{value:.1f}x"
            else:
                display_value = str(value).upper()

            line = f"{name}: < {display_value} >"
            content = Colors.accent(f"> {line}") if i == selected_index else f"  {line}"
            lines.append(self._center(content, term_width))

        lines.append("")
        lines.append(self._center("Use UP/DOWN to select, LEFT/RIGHT to change value.", term_width))
        lines.append(self._center("Press ESC to return to main menu.", term_width))
        render_screen(lines)

import re
import sys
from shutil import get_terminal_size

from ...view_utils import fit_to_width, get_visible_len, invalidate_screen, show_cursor


class SandboxView:
    MATERIAL_COLORS = {
        "wood": "\033[32m",
        "healing_herb": "\033[92m",
        "stone": "\033[90m",
        "scrap": "\033[36m",
        "crystal_shard": "\033[96m",
        "key": "\033[93m",
        "healing_potion": "\033[92m",
    }
    RESET = "\033[0m"

    def display(self, lines: list[str], prompt: str = ""):
        invalidate_screen()
        width, height = get_terminal_size(fallback=(80, 24))
        width = max(50, width)
        body = self._frame(lines, width)
        visible = body[: max(1, height - 2)]
        output = "\033[H\033[J" + "\n".join(fit_to_width(line, width) for line in visible)
        if prompt:
            output += "\n\n" + prompt
        sys.stdout.write(output)
        sys.stdout.flush()
        show_cursor()

    def message(self, title: str, lines: list[str]):
        self.display([title, "", *lines, "", "Press ENTER to continue."])
        input()

    def _frame(self, lines: list[str], width: int) -> list[str]:
        inner_width = width - 4
        framed = ["+" + "-" * (width - 2) + "+"]
        for line in lines:
            colored = self.colorize_materials(line)
            padding = max(0, inner_width - get_visible_len(colored))
            framed.append("| " + colored + " " * padding + " |")
        framed.append("+" + "-" * (width - 2) + "+")
        return framed

    def colorize_materials(self, text: str) -> str:
        output = text
        for item_id, color in self.MATERIAL_COLORS.items():
            pattern = rf"\b{re.escape(item_id)}\b"
            output = re.sub(pattern, f"{color}{item_id}{self.RESET}", output)
        return output

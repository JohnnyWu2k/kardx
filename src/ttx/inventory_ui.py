"""A centered 5 by 5 backpack over a frozen world frame."""
import curses

from kardx.view_utils import fit_to_width
from ttx.world.inventory import BACKPACK_SIZE


def backpack_frame(background, slots, counts, selected, active):
    frame = background.copy()
    if frame.rows < 12 or frame.columns < 17:
        frame.addstr(frame.rows // 2, 0, "Resize / E: close")
        return frame, []
    cell_width = min(15, (frame.columns - 4) // 5)
    cell_height = max(1, min(3, (frame.rows - 7) // 5))
    width, height = cell_width * 5 + 2, cell_height * 5 + 7
    left, top = (frame.columns - width) // 2, (frame.rows - height) // 2
    for row in range(height):
        line = "+" + "-" * (width - 2) + "+" if row in (0, height - 1) else "|" + " " * (width - 2) + "|"
        frame.addstr(top + row, left, line)
    frame.addstr(top + 1, left + 2, fit_to_width("Backpack 25   [E / Esc: close]", width - 4))
    frame.addstr(top + 2, left + 2, fit_to_width("Slots 1-10 = hotbar (10 uses key 0)", width - 4))
    targets = []
    for index in range(BACKPACK_SIZE):
        x, y = left + 1 + index % 5 * cell_width, top + 3 + index // 5 * cell_height
        targets.append((x, y, x + cell_width, y + cell_height, index))
        item = slots[index]
        label = f"{index + 1}" + (" *" if index == active else "")
        if item:
            lines = [label, item, f"x{counts.get(item, 0)}"]
            if cell_height < 3:
                lines = [f"{label}: {item}", f"x{counts.get(item, 0)}"]
        else:
            lines = [str(index + 1)]
        for dy in range(cell_height):
            text = lines[dy] if dy < len(lines) else ""
            frame.addstr(y + dy, x, fit_to_width(text, cell_width - 1).ljust(cell_width),
                         curses.A_REVERSE if index == selected else 0)
    item = slots[selected]
    detail = f"{selected + 1}: {item} x{counts.get(item, 0)}" if item else f"{selected + 1}: empty hand"
    frame.addstr(top + height - 3, left + 2, fit_to_width(detail, width - 4))
    frame.addstr(top + height - 2, left + 2, fit_to_width("Click/Enter: equip   1-9,0: swap to hotbar", width - 4))
    return frame, targets

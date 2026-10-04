"""Fixed viewports; crossing an edge advances one screen with a small overlap."""
import math


class Camera:
    def __init__(self):
        self.layout = None
        self.position = (0.0, 0.0)
        self.display_position = self.position

    def follow(self, player, visible, world, now=None):
        # A page changes in one frame. Keeping its origin fixed between edges
        # reuses cached terrain and avoids scrolling thousands of terminal cells.
        # ``now`` remains accepted for callers that also animate actor poses.
        layout = (*visible, *world)
        if layout != self.layout:
            self.position = tuple(max(0.0, min(max(0, limit - size), math.floor(p - size / 2)))
                                  for p, size, limit in zip(player, visible, world))
            self.layout = layout
        updated = []
        for p, start, size, limit in zip(player, self.position, visible, world):
            margin = min(1.0, size / 4)
            # The overlap is wider than both edge triggers, giving hysteresis
            # so a small reversal after a transition cannot flip screens.
            overlap = min(size / 2, max(4.0, min(8.0, size * 0.15)))
            stride = max(min(1.0, size / 2), math.floor(size - overlap))
            if p < start + margin:
                start -= math.ceil((start + margin - p) / stride) * stride
            elif p >= start + size - margin:
                start += (math.floor((p - start - size + margin) / stride) + 1) * stride
            updated.append(max(0.0, min(max(0, limit - size), start)))
        self.position = tuple(updated)
        self.display_position = self.position
        return self.display_position

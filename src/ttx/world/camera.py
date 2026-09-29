"""Position-based camera tracking: a stopped player never leaves a moving camera."""


class FollowAxis:
    def __init__(self, position: float, visible: float, limit: float, zone: float):
        self.camera = max(0.0, min(limit, position - visible / 2))
        self.visible, self.limit, self.zone = visible, limit, zone
        self.direction = 0
        self.anchor_player = position
        self.anchor_camera = self.camera

    def follow(self, position: float) -> float:
        if not self.direction:
            offset = position - (self.camera + self.visible / 2)
            if abs(offset) <= self.zone:
                return self.camera
            self.direction = 1 if offset > 0 else -1
            self.anchor_player = self.camera + self.visible / 2 + self.direction * self.zone
            self.anchor_camera = self.camera
        travel = self.direction * (position - self.anchor_player)
        if travel <= 0:
            self.camera = self.anchor_camera
            self.direction = 0
        else:
            # A one-tile ramp makes entering the scrolling region gradual.
            distance = travel * travel / 2 if travel < 1 else travel - 0.5
            self.camera = max(0.0, min(self.limit, self.anchor_camera + self.direction * distance))
        return self.camera


class Camera:
    def __init__(self):
        self.axes = None
        self.layout = None
        self.last_player = None

    def follow(self, player: tuple[float, float], visible: tuple[float, float],
               world: tuple[int, int]) -> tuple[float, float]:
        layout = (*visible, *world)
        teleported = self.last_player and any(abs(a - b) > size for a, b, size in zip(player, self.last_player, visible))
        if self.axes is None or layout != self.layout or teleported:
            self.axes = [FollowAxis(player[0], visible[0], max(0, world[0] - visible[0]), min(3.0, visible[0] / 6)),
                         FollowAxis(player[1], visible[1], max(0, world[1] - visible[1]), max(1.0, visible[1] / 4))]
            self.layout = layout
        self.last_player = player
        return self.axes[0].follow(player[0]), self.axes[1].follow(player[1])

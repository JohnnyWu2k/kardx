"""Render-only, distance-driven poses; never modify simulation snapshots."""
from dataclasses import dataclass

from ttx.world.physics import position


@dataclass
class ActorAnimation:
    previous: tuple | None = None
    distance: float = 0.0
    facing: int = 1
    airborne: bool = False
    landing_until: float = 0.0
    pose: str = "idle"

    def sample(self, actor, now, frozen=False):
        coordinates = actor.get("display_position", position(actor))
        dx = coordinates[0] - self.previous[0] if self.previous else 0.0
        dy = coordinates[1] - self.previous[1] if self.previous else 0.0
        teleported = abs(dx) + abs(dy) > 4
        moving = (abs(dx) > 0.0001 or (abs(actor.get("vx", 0)) > 0.015
                                      and not actor.get("horizontal_collision"))) and not teleported and not frozen
        if moving and abs(dx) > 0.0001:
            self.distance += abs(dx)
            self.facing = int(actor.get("facing", 1 if dx > 0 else -1))
        elif actor.get("facing"):
            self.facing = int(actor["facing"])
        airborne = not actor.get("grounded", abs(float(actor.get("vy", 0))) < 0.001)
        if teleported:
            self.distance = 0
            self.landing_until = 0
        elif self.airborne and not airborne and not frozen:
            self.landing_until = now + 0.10
        self.previous = coordinates
        self.airborne = airborne
        pose = self.pose if frozen else "idle"
        if not frozen:
            if airborne:
                pose = "rise" if actor.get("vy", 0) < -0.05 else "fall"
            elif now < self.landing_until:
                pose = "land"
            elif moving:
                pose = "walk"
        self.pose = pose
        return {**actor, "pose": pose, "facing": self.facing,
                "walk_frame": int(self.distance * 4) % 8}

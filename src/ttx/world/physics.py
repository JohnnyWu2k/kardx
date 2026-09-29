"""Fixed-tick motion with inertia, air control and swept grid collisions.

Velocities are tiles per 50 ms tick. Integer cells remain authoritative for
mining/combat; fractional progress preserves motion between cell crossings.
"""

import math
from collections.abc import Callable

GRAVITY = 0.16
JUMP_SPEED = -1.5
MAX_FALL_SPEED = 2.0
WALK_SPEED = 0.42
COYOTE_TICKS = 2
JUMP_BUFFER_TICKS = 3
BASE_INTERVAL = 0.05
INPUT_INTERVAL = BASE_INTERVAL / 3
INPUT_STEP = INPUT_INTERVAL / BASE_INTERVAL


def position(actor: dict) -> tuple[float, float]:
    return (float(actor["x"]) + float(actor.get("horizontal_progress", 0)),
            float(actor["y"]) + float(actor.get("vertical_progress", 0)))


def grounded(actor: dict, blocked: Callable[[int, int], bool]) -> bool:
    return (abs(float(actor.get("vertical_progress", 0))) < 1e-9 and
            blocked(int(actor["x"]), int(actor["y"]) + 1))


def jump(actor: dict, blocked: Callable[[int, int], bool]) -> bool:
    if float(actor.get("vy", 0)) < 0:
        return False
    if not grounded(actor, blocked) and actor.get("coyote_ticks", 0) <= 0:
        return False
    actor["vy"] = JUMP_SPEED
    actor["vertical_progress"] = 0.0
    actor["coyote_ticks"] = 0
    actor["jump_buffer"] = 0
    actor["grounded"] = False
    return True


def request_jump(actor: dict, blocked: Callable[[int, int], bool]):
    if not jump(actor, blocked):
        actor["jump_buffer"] = JUMP_BUFFER_TICKS


def stop_motion(actor: dict):
    """Discard input and momentum when an actor enters a card battle."""
    actor.update(move=0, vx=0.0, vy=0.0, horizontal_progress=0.0,
                 vertical_progress=0.0, jump_buffer=0, coyote_ticks=0)


def release_motion(actor: dict):
    """Release controls without snapping the actor's fractional position."""
    actor.update(move=0, vx=0.0, jump_buffer=0)


def _sweep(actor: dict, axis: str, distance: float, blocked: Callable[[int, int], bool]) -> bool:
    progress_key = "horizontal_progress" if axis == "x" else "vertical_progress"
    cell = int(actor[axis])
    start = cell + float(actor.get(progress_key, 0))
    target = start + distance
    direction = (distance > 0) - (distance < 0)
    collided = False
    if direction:
        while True:
            next_cell = cell + direction
            x, y = (next_cell, int(actor["y"])) if axis == "x" else (int(actor["x"]), next_cell)
            if blocked(x, y):
                if direction * (target - cell) > 0:
                    target = float(cell)
                    collided = True
                break
            if direction * (target - cell) <= 0.5 + 1e-9:
                break
            cell = next_cell
    actor[axis] = cell
    actor[progress_key] = target - cell
    return collided


def _accelerate(velocity: float, target: float, acceleration: float, dt: float) -> tuple[float, float]:
    """Integrate exactly, including the point at which target speed is reached."""
    delta = target - velocity
    duration = min(dt, abs(delta) / acceleration) if acceleration else 0
    change = math.copysign(acceleration, delta) if delta else 0
    next_velocity = velocity + change * duration
    distance = velocity * duration + change * duration * duration / 2
    distance += next_velocity * (dt - duration)
    return next_velocity, distance


def step_horizontal(actor: dict, blocked: Callable[[int, int], bool],
                    direction: int = 0, max_speed: float = WALK_SPEED, dt: float = 1.0):
    on_ground = grounded(actor, blocked) and float(actor.get("vy", 0)) >= 0
    velocity = float(actor.get("vx", 0))
    target = direction * max_speed
    if direction:
        acceleration = 0.63 if on_ground else 0.36
        if velocity * direction < 0:
            acceleration = 1.0 if on_ground else 0.60
        actor["facing"] = direction
    else:
        acceleration = 1.05 if on_ground else 0.48
    velocity, distance = _accelerate(velocity, target, acceleration, dt)
    collided = _sweep(actor, "x", distance, blocked)
    actor["horizontal_collision"] = collided
    if collided:
        velocity = 0.0
    actor["vx"] = velocity


def step_vertical(actor: dict, blocked: Callable[[int, int], bool], dt: float = 1.0):
    velocity = float(actor.get("vy", 0))
    if velocity >= 0 and grounded(actor, blocked):
        actor["vy"] = 0.0
        actor["vertical_progress"] = 0.0
        actor["grounded"] = True
        return
    velocity = min(MAX_FALL_SPEED, velocity)
    velocity, distance = _accelerate(velocity, MAX_FALL_SPEED, GRAVITY, dt)
    if _sweep(actor, "y", distance, blocked):
        velocity = 0.0
    actor["vy"] = velocity
    actor["grounded"] = grounded(actor, blocked) and velocity >= 0


def step_actor(actor: dict, blocked: Callable[[int, int], bool],
               direction: int = 0, max_speed: float = WALK_SPEED, dt: float = 1.0):
    if grounded(actor, blocked) and float(actor.get("vy", 0)) >= 0:
        actor["coyote_ticks"] = COYOTE_TICKS
    else:
        actor["coyote_ticks"] = max(0, actor.get("coyote_ticks", 0) - dt)
    buffered = actor.get("jump_buffer", 0)
    if buffered:
        if jump(actor, blocked):
            buffered = 0
        else:
            actor["jump_buffer"] = max(0, buffered - dt)
    step_horizontal(actor, blocked, direction, max_speed, dt)
    step_vertical(actor, blocked, dt)
    if buffered and actor.get("grounded"):
        jump(actor, blocked)

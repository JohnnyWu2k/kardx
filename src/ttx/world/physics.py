"""Fixed-tick motion with inertia, air control and swept grid collisions.

Velocities are tiles per 50 ms tick. Integer cells remain authoritative for
mining/combat; fractional progress preserves motion between cell crossings.
"""

from collections.abc import Callable

GRAVITY = 0.16
JUMP_SPEED = -1.5
MAX_FALL_SPEED = 2.0
WALK_SPEED = 0.42
COYOTE_TICKS = 2
JUMP_BUFFER_TICKS = 3


def grounded(actor: dict, blocked: Callable[[int, int], bool]) -> bool:
    return blocked(int(actor["x"]), int(actor["y"]) + 1)


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


def step_horizontal(actor: dict, blocked: Callable[[int, int], bool],
                    direction: int = 0, max_speed: float = WALK_SPEED):
    on_ground = grounded(actor, blocked) and float(actor.get("vy", 0)) >= 0
    velocity = float(actor.get("vx", 0))
    target = direction * max_speed
    if direction:
        acceleration = 0.20 if on_ground else 0.12
        if velocity * direction < 0:
            acceleration = 0.26 if on_ground else 0.16
        actor["facing"] = direction
    else:
        acceleration = 0.18 if on_ground else 0.06
    velocity += max(-acceleration, min(acceleration, target - velocity))
    progress = float(actor.get("horizontal_progress", 0)) + velocity
    # Check even a partial step: renderers must never show an actor in a wall.
    while abs(progress) > 1e-9:
        step = 1 if progress > 0 else -1
        new_x = int(actor["x"]) + step
        if blocked(new_x, int(actor["y"])):
            velocity, progress = 0.0, 0.0
            break
        if abs(progress) <= 0.5 + 1e-9:
            break
        actor["x"] = new_x
        progress -= step
    actor["vx"] = velocity
    actor["horizontal_progress"] = progress


def step_vertical(actor: dict, blocked: Callable[[int, int], bool]):
    velocity = float(actor.get("vy", 0))
    if velocity >= 0 and grounded(actor, blocked):
        actor["vy"] = 0.0
        actor["vertical_progress"] = 0.0
        actor["grounded"] = True
        return
    velocity = min(MAX_FALL_SPEED, velocity + GRAVITY)
    progress = float(actor.get("vertical_progress", 0)) + velocity
    while abs(progress) > 1e-9:
        direction = 1 if progress > 0 else -1
        new_y = int(actor["y"]) + direction
        if blocked(int(actor["x"]), new_y):
            velocity, progress = 0.0, 0.0
            break
        if abs(progress) <= 0.5 + 1e-9:
            break
        actor["y"] = new_y
        progress -= direction
    actor["vy"] = velocity
    actor["vertical_progress"] = progress
    actor["grounded"] = grounded(actor, blocked) and velocity >= 0


def step_actor(actor: dict, blocked: Callable[[int, int], bool],
               direction: int = 0, max_speed: float = WALK_SPEED):
    if grounded(actor, blocked) and float(actor.get("vy", 0)) >= 0:
        actor["coyote_ticks"] = COYOTE_TICKS
    else:
        actor["coyote_ticks"] = max(0, actor.get("coyote_ticks", 0) - 1)
    buffered = actor.get("jump_buffer", 0)
    if buffered:
        if jump(actor, blocked):
            buffered = 0
        else:
            actor["jump_buffer"] = buffered - 1
    step_horizontal(actor, blocked, direction, max_speed)
    step_vertical(actor, blocked)
    if buffered and actor.get("grounded"):
        jump(actor, blocked)

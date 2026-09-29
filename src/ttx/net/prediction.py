"""Predict local input frames and replay only inputs the server has not applied."""

from collections import deque

from ttx.world.physics import INPUT_INTERVAL, INPUT_STEP, position, release_motion, request_jump, step_actor


def apply_input(actor: dict, command: dict, blocked):
    if command.get("stop"):
        release_motion(actor)
        return
    direction = int(command.get("move", 0))
    if command.get("jump"):
        request_jump(actor, blocked)
    actor["move"] = direction
    step_actor(actor, blocked, direction, dt=INPUT_STEP)


class LocalPrediction:
    def __init__(self, actor: dict, now: float):
        self.actor = dict(actor)
        self.pending = deque()
        self.sequence = int(actor.get("input_seq", 0))
        self.last_step = now
        self.packet = None
        self.jump_pending = False

    def reconcile(self, authoritative: dict, packet, blocked):
        if packet is self.packet:
            return
        self.packet = packet
        acknowledged = int(authoritative.get("input_seq", 0))
        self.sequence = max(self.sequence, acknowledged)
        while self.pending and self.pending[0]["input_seq"] <= acknowledged:
            self.pending.popleft()
        self.actor = dict(authoritative)
        if authoritative.get("paused") or authoritative.get("battle_enemy"):
            self.pending.clear()
            self.jump_pending = False
            return
        for command in self.pending:
            apply_input(self.actor, command, blocked)

    def advance(self, now: float, direction: int, jumped: bool, blocked, send):
        self.jump_pending |= jumped
        if self.actor.get("paused") or self.actor.get("battle_enemy"):
            self.last_step = now
            return
        # Never turn a menu or a stalled renderer into a burst of old movement.
        if now - self.last_step > 0.2:
            self.last_step = now - INPUT_INTERVAL
        for _ in range(8):
            # Reserve one queue slot for an immediate menu/build release.
            if now - self.last_step < INPUT_INTERVAL - 1e-9 or len(self.pending) >= 59:
                break
            self.sequence += 1
            command = {"input_seq": self.sequence, "move": direction}
            if self.jump_pending:
                command["jump"] = True
                self.jump_pending = False
            apply_input(self.actor, command, blocked)
            self.pending.append(command)
            send(command)
            self.last_step += INPUT_INTERVAL

    def release(self, now: float):
        release_motion(self.actor)
        self.jump_pending = False
        self.last_step = now
        if self.pending and self.pending[-1].get("stop"):
            return None
        self.sequence += 1
        command = {"input_seq": self.sequence, "move": 0, "stop": True}
        self.pending.append(command)
        return command

    def resume(self, authoritative: dict, now: float):
        self.actor = dict(authoritative)
        self.actor.pop("paused", None)
        self.pending.clear()
        self.last_step = now
        self.jump_pending = False


class RemoteInterpolation:
    def __init__(self):
        self.packet = None
        self.from_positions = {}
        self.to_positions = {}
        self.started = 0.0

    def update(self, state: dict, now: float):
        if state is self.packet:
            return
        old = self.positions(now)
        self.packet = state
        self.started = float(state.get("received_at", now))
        self.to_positions = {(group, actor_id): position(actor)
                             for group in ("players", "enemies")
                             for actor_id, actor in state.get(group, {}).items()}
        self.from_positions = {key: old.get(key, value) for key, value in self.to_positions.items()}

    def positions(self, now: float) -> dict:
        alpha = max(0.0, min(1.0, (now - self.started) / 0.05))
        return {key: (self.from_positions.get(key, target)[0] * (1 - alpha) + target[0] * alpha,
                      self.from_positions.get(key, target)[1] * (1 - alpha) + target[1] * alpha)
                for key, target in self.to_positions.items()}

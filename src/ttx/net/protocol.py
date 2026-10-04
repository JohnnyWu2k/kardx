"""Bounded newline-delimited JSON framing shared by both network endpoints."""

import json
import math
from ttx.world.inventory import valid_order

COMMAND_LIMIT = 64 * 1024
SNAPSHOT_LIMIT = 16 * 1024 * 1024


class ProtocolError(ValueError):
    pass


def _reject_constant(value):
    raise ProtocolError(f"Invalid JSON number: {value}")


class JsonLineReader:
    def __init__(self, limit: int):
        self.limit = limit
        self.buffer = bytearray()

    def feed(self, data: bytes):
        self.buffer.extend(data)
        while True:
            end = self.buffer.find(b"\n")
            if end < 0:
                if len(self.buffer) > self.limit:
                    raise ProtocolError("Message exceeds size limit.")
                return
            if end > self.limit:
                raise ProtocolError("Message exceeds size limit.")
            line = bytes(self.buffer[:end])
            del self.buffer[:end + 1]
            if not line.strip():
                continue
            try:
                message = json.loads(line.decode("utf-8"), parse_constant=_reject_constant)
            except (ValueError, RecursionError) as exc:
                raise ProtocolError("Invalid JSON message.") from exc
            if not isinstance(message, dict):
                raise ProtocolError("Message must be a JSON object.")
            yield message


def valid_command(message) -> bool:
    """Reject malformed fields before a handler can partially mutate the world."""
    if not isinstance(message, dict):
        return False
    if "inventory_order" in message and not valid_order(message["inventory_order"]):
        return False
    if "tool" in message and message["tool"] is not None and message["tool"] not in ("wood_pickaxe", "stone_pickaxe", "iron_pickaxe"):
        return False
    for key in ("pause", "build", "attack", "gather", "jump", "stop", "disconnect", "defeated", "save"):
        if key in message and type(message[key]) is not bool:
            return False
    if "hello" in message and (not isinstance(message["hello"], str) or len(message["hello"]) != 32 or any(c not in "0123456789abcdef" for c in message["hello"])):
        return False
    if "craft" in message and (not isinstance(message["craft"], str) or len(message["craft"]) > 40):
        return False
    if "card_progress" in message:
        progress = message["card_progress"]
        if not isinstance(progress, dict) or set(progress) != {"hp", "max_hp", "mana", "deck", "rewards_received"}:
            return False
        if any(type(progress[k]) is not int or not 1 <= progress[k] <= 100000 for k in ("hp", "max_hp", "mana")):
            return False
        if type(progress["rewards_received"]) is not int or not 0 <= progress["rewards_received"] <= 100000:
            return False
        if not isinstance(progress["deck"], list) or len(progress["deck"]) > 5000 or any(not isinstance(card, str) or len(card) > 100 for card in progress["deck"]):
            return False
    for key in ("move", "dx", "dy"):
        if key in message and (type(message[key]) is not int or message[key] not in (-1, 0, 1)):
            return False
    for key in ("x", "y"):
        if key in message and type(message[key]) is not int:
            return False
    if "input_seq" in message and (type(message["input_seq"]) is not int or not 0 < message["input_seq"] < 2**63):
        return False
    if "enemy_id" in message and not isinstance(message["enemy_id"], str):
        return False
    if "material" in message and not isinstance(message["material"], str):
        return False
    if "battle" in message and message["battle"] not in ("start", "end"):
        return False
    if "damage" in message and (type(message["damage"]) is not int or not 0 < message["damage"] <= 1_000_000):
        return False
    return True


def valid_snapshot(state: dict) -> bool:
    if not isinstance(state, dict):
        return False
    if not isinstance(state.get("client_id"), str) or type(state.get("map_seed")) is not int:
        return False
    for key in ("world_width", "world_height"):
        if type(state.get(key)) is not int or not 0 < state[key] <= 1_000_000:
            return False
    for key in ("tick", "terrain_revision"):
        if key in state and (type(state[key]) is not int or state[key] < 0):
            return False
    if "world_paused" in state and type(state["world_paused"]) is not bool:
        return False
    for group in ("players", "enemies", "objects", "custom_tiles"):
        actors = state.get(group)
        if not isinstance(actors, dict):
            return False
        for actor in actors.values():
            if not isinstance(actor, dict) or any(type(actor.get(axis)) is not int for axis in ("x", "y")):
                return False
            if not (0 <= actor["x"] < state["world_width"] and 0 <= actor["y"] < state["world_height"]):
                return False
            for key in ("vx", "vy", "horizontal_progress", "vertical_progress", "coyote_ticks", "jump_buffer"):
                value = actor.get(key, 0)
                if type(value) not in (int, float) or abs(value) > 1_000_000 or not math.isfinite(value):
                    return False
                if key in ("coyote_ticks", "jump_buffer") and value < 0:
                    return False
            for key in ("move", "facing", "direction"):
                if key in actor and (type(actor[key]) is not int or actor[key] not in (-1, 0, 1)):
                    return False
            for key in ("paused", "pause_requested"):
                if key in actor and type(actor[key]) is not bool:
                    return False
            if group == "custom_tiles" and actor.get("char") not in ('.', '"', ':', '#', '%', 'o', '*', '|', 'c', 'l', 'W'):
                return False
            if group == "players":
                if "inventory_order" in actor and not valid_order(actor["inventory_order"]):
                    return False
                inventory = actor.get("inventory", {})
                if not isinstance(inventory, dict) or any(type(amount) is not int or amount < 0 for amount in inventory.values()):
                    return False
                for key in ("input_seq", "input_received_seq", "hp", "gold"):
                    if key in actor and (type(actor[key]) is not int or actor[key] < 0):
                        return False
                cards = actor.get("cards", [])
                if not isinstance(cards, list) or any(not isinstance(card, str) for card in cards):
                    return False
    return state["client_id"] in state["players"]

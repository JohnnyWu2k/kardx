from __future__ import annotations

import json
import random
import re
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .game_state import Game
from .loader import get_user_data_dir, load_game_data
from .persistence import atomic_write_text


@dataclass
class RunState:
    player_id: str
    player_name: str
    max_hp: int
    current_hp: int
    base_mana: int
    deck_ids: list[str]
    current_room: str
    gold: int = 0
    inventory: dict[str, int] = field(default_factory=dict)
    flags: set[str] = field(default_factory=set)
    quests: dict[str, str] = field(default_factory=dict)
    defeated_encounters: set[str] = field(default_factory=set)
    visited_rooms: set[str] = field(default_factory=set)
    forage_cooldowns: dict[str, int] = field(default_factory=dict)
    room_items: dict[str, list[str]] = field(default_factory=dict)
    turn_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return deepcopy({
            "player_id": self.player_id,
            "player_name": self.player_name,
            "max_hp": self.max_hp,
            "current_hp": self.current_hp,
            "base_mana": self.base_mana,
            "deck_ids": self.deck_ids,
            "current_room": self.current_room,
            "gold": self.gold,
            "inventory": self.inventory,
            "flags": sorted(self.flags),
            "quests": self.quests,
            "defeated_encounters": sorted(self.defeated_encounters),
            "visited_rooms": sorted(self.visited_rooms),
            "forage_cooldowns": self.forage_cooldowns,
            "room_items": self.room_items,
            "turn_count": self.turn_count,
        })

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RunState:
        if not isinstance(payload, dict):
            raise ValueError("Save data must be an object.")

        def text(value, field):
            if not isinstance(value, str) or not value:
                raise ValueError(f"Invalid save field '{field}': expected a nonempty string.")
            return value

        def number(value, field, minimum=0):
            if type(value) is not int or value < minimum:
                raise ValueError(f"Invalid save field '{field}': expected an integer >= {minimum}.")
            return value

        def strings(value, field):
            if not isinstance(value, list):
                raise ValueError(f"Invalid save field '{field}': expected a list.")
            return [text(item, field) for item in value]

        def mapping(value, field, validate):
            if not isinstance(value, dict):
                raise ValueError(f"Invalid save field '{field}': expected an object.")
            return {text(key, field): validate(item, field) for key, item in value.items()}

        player_id = text(payload.get("player_id"), "player_id")
        max_hp = number(payload.get("max_hp"), "max_hp", 1)
        current_hp = number(payload.get("current_hp"), "current_hp", 1)
        if current_hp > max_hp:
            raise ValueError("Invalid save field 'current_hp': exceeds max_hp.")
        return cls(
            player_id=player_id,
            player_name=text(payload.get("player_name", player_id), "player_name"),
            max_hp=max_hp,
            current_hp=current_hp,
            base_mana=number(payload.get("base_mana"), "base_mana"),
            deck_ids=strings(payload.get("deck_ids"), "deck_ids"),
            current_room=text(payload.get("current_room"), "current_room"),
            gold=number(payload.get("gold", 0), "gold"),
            inventory=mapping(payload.get("inventory", {}), "inventory", number),
            flags=set(strings(payload.get("flags", []), "flags")),
            quests=mapping(payload.get("quests", {}), "quests", text),
            defeated_encounters=set(strings(payload.get("defeated_encounters", []), "defeated_encounters")),
            visited_rooms=set(strings(payload.get("visited_rooms", []), "visited_rooms")),
            forage_cooldowns=mapping(payload.get("forage_cooldowns", {}), "forage_cooldowns", number),
            room_items=mapping(payload.get("room_items", {}), "room_items", strings),
            turn_count=number(payload.get("turn_count", 0), "turn_count"),
        )

    def add_item(self, item_id: str, amount: int = 1):
        if amount == 0:
            return
        current = self.inventory.get(item_id, 0) + amount
        if current <= 0:
            self.inventory.pop(item_id, None)
        else:
            self.inventory[item_id] = current

    def has_items(self, required: dict[str, int]) -> bool:
        return all(self.inventory.get(item_id, 0) >= amount for item_id, amount in required.items())


class SandboxData:
    def __init__(self):
        self.world = load_game_data("world.jsonc") or {}
        self.recipes = load_game_data("recipes.jsonc") or {}
        self.encounters = load_game_data("encounters.jsonc") or {}
        self.cards = {
            item["id"]: item
            for item in (load_game_data("cards.jsonc") or [])
            if isinstance(item, dict) and item.get("id")
        }
        self.characters = load_game_data("characters.jsonc") or {}

    @property
    def rooms(self) -> dict[str, dict]:
        return self.world.get("rooms", {})

    @property
    def start_room(self) -> str:
        return self.world.get("start", "")

    def create_state(self, player_id: str) -> RunState:
        player = self.characters.get(player_id)
        if not player:
            raise ValueError(f"Unknown player '{player_id}'.")
        deck_ids: list[str] = []
        for card_id, count in player.get("deck", {}).items():
            deck_ids.extend([card_id] * int(count))
        state = RunState(
            player_id=player_id,
            player_name=player.get("display_name", player_id),
            max_hp=int(player.get("hp", 10)),
            current_hp=int(player.get("hp", 10)),
            base_mana=int(player.get("mana", 3)),
            deck_ids=deck_ids,
            current_room=self.start_room,
            gold=0,
            room_items={
                room_id: list(room.get("items", []))
                for room_id, room in self.rooms.items()
            },
        )
        state.visited_rooms.add(state.current_room)
        return state

    def validate(self) -> list[str]:
        errors: list[str] = []
        rooms = self.rooms
        if self.start_room not in rooms:
            errors.append(f"World start room '{self.start_room}' does not exist.")
        for room_id, room in rooms.items():
            for direction, target in room.get("exits", {}).items():
                if target not in rooms:
                    errors.append(f"Room '{room_id}' exit '{direction}' targets missing room '{target}'.")
            for talk_def in room.get("talk", {}).values():
                for effect in talk_def.get("effects", []):
                    self._validate_effect(effect, errors, f"room '{room_id}' talk")
        for recipe_id, recipe in self.recipes.items():
            costs = recipe.get("requires", {})
            if not isinstance(costs, dict) or any(type(amount) is not int or amount <= 0 for amount in costs.values()):
                errors.append(f"Recipe '{recipe_id}' material costs must be positive integers.")
            for effect in recipe.get("effects", []):
                self._validate_effect(effect, errors, f"recipe '{recipe_id}'")
        for encounter_id, encounter in self.encounters.items():
            room_id = encounter.get("room")
            enemy_id = encounter.get("enemy")
            if room_id not in rooms:
                errors.append(f"Encounter '{encounter_id}' references missing room '{room_id}'.")
            if enemy_id not in self.characters:
                errors.append(f"Encounter '{encounter_id}' references missing enemy '{enemy_id}'.")
            retreat_room = encounter.get("retreat_room")
            if retreat_room is not None and retreat_room not in rooms:
                errors.append(f"Encounter '{encounter_id}' references missing retreat room '{retreat_room}'.")
            for card_id in encounter.get("card_rewards", []):
                if card_id not in self.cards:
                    errors.append(f"Encounter '{encounter_id}' rewards missing card '{card_id}'.")
            for effect in encounter.get("on_win", []):
                self._validate_effect(effect, errors, f"encounter '{encounter_id}'")
        return errors

    def _validate_effect(self, effect: dict, errors: list[str], source: str):
        action = effect.get("action")
        if action == "add_card":
            card_id = effect.get("card")
            if card_id not in self.cards:
                errors.append(f"{source} adds missing card '{card_id}'.")
        elif action == "upgrade_card":
            from_card = effect.get("from")
            to_card = effect.get("to")
            if from_card not in self.cards:
                errors.append(f"{source} upgrades missing card '{from_card}'.")
            if to_card not in self.cards:
                errors.append(f"{source} upgrades to missing card '{to_card}'.")


class SandboxGame:
    def __init__(
        self,
        data: SandboxData | None = None,
        state: RunState | None = None,
        rng: random.Random | None = None,
    ):
        self.data = data or SandboxData()
        self.state = state
        self.rng = rng or random.Random()

    def start(self, player_id: str) -> RunState:
        self.state = self.data.create_state(player_id)
        return self.state

    def room(self) -> dict:
        self._require_state()
        return self.data.rooms[self.state.current_room]

    def ground_items(self) -> list[str]:
        self._require_state()
        return self.state.room_items.setdefault(
            self.state.current_room,
            list(self.room().get("items", [])),
        )

    def look_lines(self) -> list[str]:
        room = self.room()
        items = sorted(item for item, amount in self.state.inventory.items() if amount > 0)
        lines = [
            f"{room.get('name', self.state.current_room)}",
            room.get("desc", ""),
            "",
            "Exits: " + ", ".join(sorted(room.get("exits", {}))) if room.get("exits") else "Exits: none",
        ]
        ground_items = self.ground_items()
        if ground_items:
            lines.append("On the ground: " + ", ".join(ground_items))
        if room.get("forage"):
            lines.append("This area can be foraged.")
        lines.extend([
            "",
            f"HP: {self.state.current_hp}/{self.state.max_hp}  Gold: {self.state.gold}  Deck: {len(self.state.deck_ids)}",
            "Inventory: " + (", ".join(items) if items else "empty"),
        ])
        return lines

    def go(self, direction: str) -> list[str]:
        room = self.room()
        exits = room.get("exits", {})
        if direction not in exits:
            return ["You can't go that way."]
        lock = room.get("locked_exits", {}).get(direction)
        unlock_flag = self._unlock_flag(self.state.current_room, direction)
        if lock and unlock_flag not in self.state.flags:
            return [lock.get("message", "That way is locked.")]
        self.state.current_room = exits[direction]
        self.state.visited_rooms.add(self.state.current_room)
        self.state.turn_count += 1
        return [f"You travel {direction}.", *self.look_lines()]

    def take(self, item_id: str) -> list[str]:
        items = self.ground_items()
        if item_id not in items:
            return [f"There is no '{item_id}' here."]
        items.remove(item_id)
        self.state.add_item(item_id)
        return [f"Taken: {item_id}."]

    def use(self, item_id: str) -> list[str]:
        if self.state.inventory.get(item_id, 0) <= 0:
            return [f"You don't have '{item_id}'."]
        for direction, lock in self.room().get("locked_exits", {}).items():
            if lock.get("requires_item") == item_id:
                self.state.flags.add(self._unlock_flag(self.state.current_room, direction))
                return [f"You unlock the way to the {direction}."]
        if item_id == "healing_potion":
            before = self.state.current_hp
            self.state.current_hp = min(self.state.max_hp, self.state.current_hp + 12)
            self.state.add_item("healing_potion", -1)
            return [f"You recover {self.state.current_hp - before} HP."]
        return ["Nothing happens."]

    def forage(self) -> list[str]:
        room = self.room()
        forage = room.get("forage", [])
        if not forage:
            return ["There is nothing useful to forage here."]
        next_allowed = self.state.forage_cooldowns.get(self.state.current_room, 0)
        if self.state.turn_count < next_allowed:
            return ["This area has been picked clean for now."]
        total = sum(max(0, int(item.get("weight", 1))) for item in forage)
        if total <= 0:
            return ["There is nothing useful to forage here."]
        roll = self.rng.randint(1, total)
        cursor = 0
        found = forage[-1]["item"]
        for item in forage:
            cursor += max(0, int(item.get("weight", 1)))
            if roll <= cursor:
                found = item["item"]
                break
        self.state.add_item(found)
        self.state.turn_count += 1
        self.state.forage_cooldowns[self.state.current_room] = self.state.turn_count + 3
        return [f"You forage and find: {found}."]

    def craft(self, recipe_id: str) -> list[str]:
        self._require_state()
        recipe = self.data.recipes.get(recipe_id)
        if not recipe:
            return [f"Unknown recipe: {recipe_id}."]
        required = recipe.get("requires", {})
        if not isinstance(required, dict) or any(type(amount) is not int or amount <= 0 for amount in required.values()):
            return [f"Recipe '{recipe_id}' has invalid material costs."]
        if not self.state.has_items(required):
            needs = ", ".join(f"{amount} {item_id}" for item_id, amount in required.items())
            return [f"Need: {needs}."]
        deck = list(self.state.deck_ids)
        for effect in recipe.get("effects", []):
            if effect.get("action") == "upgrade_card":
                source, target = effect.get("from"), effect.get("to")
                if source not in deck:
                    return [f"No {self.card_name(source)} available to upgrade."]
                if target not in self.data.cards:
                    return [f"Unknown card: {target}."]
                deck.remove(source)
                deck.append(target)
            elif effect.get("action") == "add_card":
                card_id = effect.get("card")
                if card_id not in self.data.cards:
                    return [f"Unknown card: {card_id}."]
                deck.append(card_id)
        for item_id, amount in required.items():
            self.state.add_item(item_id, -amount)
        messages = [f"Crafted: {recipe.get('name', recipe_id)}."]
        messages.extend(self.apply_effects(recipe.get("effects", [])))
        self.state.turn_count += 1
        return messages

    def talk(self, target: str | None = None) -> list[str]:
        talks = self.room().get("talk", {})
        if not talks:
            return ["No one seems around to talk to."]
        if not target:
            target = next(iter(talks))
        talk_def = talks.get(target)
        if not talk_def:
            return [f"No one named '{target}' is here."]
        messages = list(talk_def.get("text", []))
        messages.extend(self.apply_effects(talk_def.get("effects", [])))
        return messages

    def journal_lines(self) -> list[str]:
        if not self.state.quests:
            return ["Journal: no active quests."]
        return [
            "Journal:",
            *[
                f"- {quest}: {status}"
                for quest, status in sorted(self.state.quests.items())
            ],
        ]

    def inventory_lines(self) -> list[str]:
        if not self.state.inventory:
            return ["Inventory is empty."]
        return [
            "Inventory:",
            *[
                f"- {item_id}: {amount}"
                for item_id, amount in sorted(self.state.inventory.items())
                if amount > 0
            ],
        ]

    def deck_lines(self) -> list[str]:
        counts: dict[str, int] = {}
        for card_id in self.state.deck_ids:
            counts[card_id] = counts.get(card_id, 0) + 1
        return [
            "Deck:",
            *[
                f"- {self.card_name(card_id)} x{count}"
                for card_id, count in sorted(counts.items())
            ],
        ]

    def pending_encounter_id(self) -> str | None:
        self._require_state()
        for encounter_id, encounter in self.data.encounters.items():
            if encounter.get("room") != self.state.current_room:
                continue
            if not encounter.get("repeatable", False) and encounter_id in self.state.defeated_encounters:
                continue
            required = set(encounter.get("requires_flags", []))
            if not required.issubset(self.state.flags):
                continue
            return encounter_id
        return None

    def apply_encounter_victory(self, encounter_id: str) -> list[str]:
        encounter = self.data.encounters[encounter_id]
        self.state.defeated_encounters.add(encounter_id)
        messages = [f"Victory: {encounter.get('label', encounter_id)}."]
        messages.extend(self.apply_effects(encounter.get("on_win", [])))
        rewards = [card_id for card_id in encounter.get("card_rewards", []) if card_id in self.data.cards]
        if rewards:
            card_id = self.rng.choice(rewards)
            self.state.deck_ids.append(card_id)
            messages.append(f"Added card reward: {self.card_name(card_id)}.")
        return messages

    def apply_encounter_defeat(self, encounter_id: str) -> list[str]:
        encounter = self.data.encounters[encounter_id]
        retreat_room = encounter.get("retreat_room")
        if retreat_room in self.data.rooms:
            self.state.current_room = retreat_room
            self.state.visited_rooms.add(retreat_room)
            return [f"You retreat to {self.data.rooms[retreat_room].get('name', retreat_room)}."]
        return ["You survive, barely."]

    def apply_effects(self, effects: list[dict]) -> list[str]:
        messages: list[str] = []
        for effect in effects:
            action = effect.get("action")
            value = int(effect.get("value", 0))
            if action == "add_item":
                amount = int(effect.get("value", 1))
                item_id = effect.get("item")
                self.state.add_item(item_id, amount)
                messages.append(f"Item {'+' if amount >= 0 else ''}{amount}: {item_id}.")
            elif action == "add_gold":
                self.state.gold = max(0, self.state.gold + value)
                messages.append(f"Gold {'+' if value >= 0 else ''}{value}.")
            elif action == "add_card":
                card_id = effect.get("card")
                if card_id in self.data.cards:
                    self.state.deck_ids.append(card_id)
                    messages.append(f"Added card: {self.card_name(card_id)}.")
            elif action == "upgrade_card":
                from_card = effect.get("from")
                to_card = effect.get("to")
                if from_card in self.state.deck_ids and to_card in self.data.cards:
                    self.state.deck_ids.remove(from_card)
                    self.state.deck_ids.append(to_card)
                    messages.append(f"{self.card_name(from_card)} became {self.card_name(to_card)}.")
                else:
                    messages.append(f"No {self.card_name(from_card)} available to upgrade.")
            elif action == "set_flag":
                flag = effect.get("flag")
                if flag:
                    self.state.flags.add(flag)
            elif action == "start_quest":
                quest = effect.get("quest")
                if quest:
                    self.state.quests.setdefault(quest, "active")
            elif action == "complete_quest":
                quest = effect.get("quest")
                if quest:
                    self.state.quests[quest] = "complete"
        return messages

    def save(self, slot: str = "sandbox", save_dir: Path | None = None) -> Path:
        self._require_state()
        path = self._save_path(slot, save_dir)
        atomic_write_text(path, json.dumps(self.state.to_dict(), indent=2))
        return path

    def load(self, slot: str = "sandbox", save_dir: Path | None = None) -> RunState:
        path = self._save_path(slot, save_dir)
        payload = json.loads(path.read_text(encoding="utf-8"))
        state = RunState.from_dict(payload)
        if state.current_room not in self.data.rooms:
            raise ValueError(f"Save references missing room '{state.current_room}'.")
        if state.player_id not in self.data.characters:
            raise ValueError(f"Save references missing player '{state.player_id}'.")
        missing_cards = set(state.deck_ids) - self.data.cards.keys()
        if missing_cards:
            raise ValueError(f"Save references missing cards: {', '.join(sorted(missing_cards))}.")
        self.state = state
        return self.state

    @staticmethod
    def _save_path(slot: str, save_dir: Path | None) -> Path:
        if not isinstance(slot, str) or not re.fullmatch(r"[\w-]{1,64}", slot):
            raise ValueError("Save slot must contain 1-64 letters, numbers, underscores or hyphens.")
        base_dir = save_dir if save_dir is not None else get_user_data_dir().parent / "saves"
        return base_dir / f"{slot}.json"

    def card_name(self, card_id: str | None) -> str:
        if not card_id:
            return "Unknown"
        return self.data.cards.get(card_id, {}).get("name", card_id)

    def _unlock_flag(self, room_id: str, direction: str) -> str:
        return f"unlocked:{room_id}:{direction}"

    def _require_state(self):
        if self.state is None:
            raise RuntimeError("Sandbox game has not been started.")


class BattleSession:
    def __init__(self, sandbox: SandboxGame, encounter_id: str):
        sandbox._require_state()
        self.sandbox = sandbox
        self.encounter_id = encounter_id
        self.encounter = sandbox.data.encounters[encounter_id]
        self.game = Game(
            player_id=sandbox.state.player_id,
            enemy_id=self.encounter["enemy"],
            player_deck_ids=sandbox.state.deck_ids,
            player_hp=sandbox.state.current_hp,
            player_max_hp=sandbox.state.max_hp,
            player_base_mana=sandbox.state.base_mana,
        )

    def sync_state(self):
        player = self.game.player
        if not player:
            return
        self.sandbox.state.current_hp = max(1, player.hp)
        self.sandbox.state.base_mana = max(0, player.max_mana)
        all_cards = list(player.deck) + list(player.hand) + list(player.discard_pile)
        self.sandbox.state.deck_ids = [card.id for card in all_cards]

    def finish(self, result: str) -> list[str]:
        self.sync_state()
        if result == "victory":
            return self.sandbox.apply_encounter_victory(self.encounter_id)
        return self.sandbox.apply_encounter_defeat(self.encounter_id)

from dataclasses import dataclass, field
from random import choice, choices, sample

from .card import Card
from .loader import load_game_data


@dataclass
class AdventureNode:
    id: str
    type: str
    label: str
    enemy: str | None = None
    event: str | None = None
    gold: int = 0
    relic: bool = False


@dataclass
class AdventureState:
    adventure_id: str
    name: str
    player_id: str
    player_name: str
    max_hp: int
    current_hp: int
    base_mana: int
    deck_ids: list[str]
    map_rows: list[list[AdventureNode]]
    card_reward_pool: list[str]
    shop_card_pool: list[str]
    relic_pool: list[str]
    gold: int = 0
    relic_ids: list[str] = field(default_factory=list)
    defeated_enemies: list[str] = field(default_factory=list)
    visited_nodes: list[AdventureNode] = field(default_factory=list)
    event_flags: set[str] = field(default_factory=set)
    row_index: int = 0

    @property
    def current_nodes(self) -> list[AdventureNode]:
        if self.row_index >= len(self.map_rows):
            return []
        return self.map_rows[self.row_index]

    @property
    def is_complete(self) -> bool:
        return self.row_index >= len(self.map_rows)

    def advance(self):
        self.row_index += 1

    def card_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for card_id in self.deck_ids:
            counts[card_id] = counts.get(card_id, 0) + 1
        return counts


class AdventureData:
    def __init__(self):
        self.cards: dict[str, Card] = {
            item["id"]: Card(**item) for item in (load_game_data("cards.jsonc") or [])
        }
        self.characters = load_game_data("characters.jsonc") or {}
        self.adventures = load_game_data("adventures.jsonc") or {}
        self.events = load_game_data("events.jsonc") or {}
        self.relics = load_game_data("relics.jsonc") or {}

    def create_state(self, player_id: str, adventure_id: str = "default") -> AdventureState:
        char_def = self.characters.get(player_id)
        adv_def = self.adventures.get(adventure_id)
        if not char_def:
            raise ValueError(f"Unknown player '{player_id}'.")
        if not adv_def:
            raise ValueError(f"Unknown adventure '{adventure_id}'.")

        deck_ids: list[str] = []
        for card_id, count in char_def.get("deck", {}).items():
            deck_ids.extend([card_id] * count)
        deck_ids = self._apply_starting_card_limits(deck_ids, adv_def)

        map_rows = self._create_map_rows(adv_def)

        return AdventureState(
            adventure_id=adventure_id,
            name=adv_def.get("name", "Unnamed Adventure"),
            player_id=player_id,
            player_name=char_def.get("display_name", player_id),
            max_hp=char_def.get("hp", 10),
            current_hp=char_def.get("hp", 10),
            base_mana=char_def.get("mana", 3),
            deck_ids=deck_ids,
            map_rows=map_rows,
            card_reward_pool=self._card_reward_pool(adv_def),
            shop_card_pool=self._shop_card_pool(adv_def),
            relic_pool=adv_def.get("relic_rewards", list(self.relics.keys())),
            gold=adv_def.get("starting_gold", 0),
        )

    def _apply_starting_card_limits(self, deck_ids: list[str], adv_def: dict) -> list[str]:
        limits = adv_def.get("starting_card_limits", {})
        replacements = adv_def.get("starting_card_replacements", {})
        limited_deck = list(deck_ids)
        for card_id, max_count in limits.items():
            overflow = max(0, limited_deck.count(card_id) - int(max_count))
            for _ in range(overflow):
                limited_deck.remove(card_id)
                replacement = replacements.get(card_id)
                if replacement in self.cards:
                    limited_deck.append(replacement)
        return limited_deck

    def _card_reward_pool(self, adv_def: dict) -> list[str]:
        pool = [
            card_id for card_id in adv_def.get("card_rewards", [])
            if card_id in self.cards
        ]
        for card_id in self.cards:
            if card_id not in pool:
                pool.append(card_id)
        return pool

    def _shop_card_pool(self, adv_def: dict) -> list[str]:
        configured = adv_def.get("shop_cards", adv_def.get("card_rewards", []))
        pool = [
            card_id for card_id in configured
            if card_id in self.cards and self.cards[card_id].rarity != "rare"
        ]
        for card_id, card in self.cards.items():
            if card.rarity != "rare" and card_id not in pool:
                pool.append(card_id)
        return pool

    def _create_map_rows(self, adv_def: dict) -> list[list[AdventureNode]]:
        if adv_def.get("map_template") and adv_def.get("node_pools"):
            return self._generate_map_rows(adv_def)
        return [
            [AdventureNode(**node_def) for node_def in row]
            for row in adv_def.get("map", [])
        ]

    def _generate_map_rows(self, adv_def: dict) -> list[list[AdventureNode]]:
        pools = adv_def.get("node_pools", {})
        rows: list[list[AdventureNode]] = []
        for row_index, row_template in enumerate(adv_def.get("map_template", [])):
            row = []
            used_ids_by_type: dict[str, set[str]] = {}
            for slot_index, node_spec in enumerate(row_template):
                if isinstance(node_spec, str):
                    node_type = node_spec
                    used_ids = used_ids_by_type.setdefault(node_type, set())
                    pool = [
                        item for item in pools.get(node_type, [])
                        if item.get("id") not in used_ids
                    ] or pools.get(node_type, [])
                    if not pool:
                        continue
                    node_def = dict(choice(pool))
                else:
                    node_def = dict(node_spec)
                    node_type = node_def.get("type")
                    if node_type and len(node_def) == 1:
                        used_ids = used_ids_by_type.setdefault(node_type, set())
                        pool = [
                            item for item in pools.get(node_type, [])
                            if item.get("id") not in used_ids
                        ] or pools.get(node_type, [])
                        if not pool:
                            continue
                        node_def = dict(choice(pool))
                used_ids_by_type.setdefault(node_def.get("type", "node"), set()).add(node_def.get("id", ""))
                node_def["id"] = f"{node_def.get('id', node_def.get('type', 'node'))}_{row_index}_{slot_index}"
                row.append(AdventureNode(**node_def))
            rows.append(row)
        return rows

    def card_name(self, card_id: str) -> str:
        card = self.cards.get(card_id)
        return card.name if card else card_id

    def relic_name(self, relic_id: str) -> str:
        relic = self.relics.get(relic_id, {})
        return relic.get("name", relic_id)

    def relic_description(self, relic_id: str) -> str:
        relic = self.relics.get(relic_id, {})
        return relic.get("description", "")

    def card_reward_options(self, state: AdventureState, count: int = 3) -> list[str]:
        pool = [card_id for card_id in state.card_reward_pool if card_id in self.cards]
        if not pool:
            return []
        if len(pool) <= count:
            return list(pool)
        picks = []
        remaining = list(pool)
        weights_by_rarity = {"common": 6, "uncommon": 3, "rare": 1}
        while remaining and len(picks) < count:
            weights = [
                weights_by_rarity.get(self.cards[card_id].rarity, 6)
                for card_id in remaining
            ]
            picked = choices(remaining, weights=weights, k=1)[0]
            picks.append(picked)
            remaining.remove(picked)
        return picks

    def available_relics(self, state: AdventureState) -> list[str]:
        return [
            relic_id
            for relic_id in state.relic_pool
            if relic_id in self.relics and relic_id not in state.relic_ids
        ]

    def random_relic(self, state: AdventureState) -> str | None:
        available = self.available_relics(state)
        if not available:
            return None
        return choice(available)

    def battle_modifiers(self, state: AdventureState) -> dict[str, int]:
        modifiers = {
            "max_mana_bonus": 0,
            "start_def_bonus": 0,
            "first_attack_damage_bonus": 0,
        }
        for relic_id in state.relic_ids:
            for effect in self.relics.get(relic_id, {}).get("effects", []):
                action = effect.get("action")
                value = int(effect.get("value", 0))
                if action == "battle_max_mana":
                    modifiers["max_mana_bonus"] += value
                elif action == "battle_start_def":
                    modifiers["start_def_bonus"] += value
                elif action == "first_attack_damage":
                    modifiers["first_attack_damage_bonus"] += value
        return modifiers

    def apply_after_battle_relics(self, state: AdventureState) -> list[str]:
        messages = []
        for relic_id in state.relic_ids:
            for effect in self.relics.get(relic_id, {}).get("effects", []):
                if effect.get("action") == "after_battle_heal":
                    value = int(effect.get("value", 0))
                    before = state.current_hp
                    state.current_hp = min(state.max_hp, state.current_hp + value)
                    healed = state.current_hp - before
                    if healed > 0:
                        messages.append(f"{self.relic_name(relic_id)} heals {healed} HP.")
        return messages

    def apply_event_results(self, state: AdventureState, results: list[dict]) -> list[str]:
        messages = []
        for result in results:
            action = result.get("action")
            value = int(result.get("value", 0))
            if action == "add_hp":
                before = state.current_hp
                state.current_hp = max(1, min(state.max_hp, state.current_hp + value))
                changed = state.current_hp - before
                messages.append(f"HP {'+' if changed >= 0 else ''}{changed}.")
            elif action == "add_gold":
                state.gold = max(0, state.gold + value)
                messages.append(f"Gold {'+' if value >= 0 else ''}{value}.")
            elif action == "add_card":
                card_id = result.get("card")
                if card_id in self.cards:
                    state.deck_ids.append(card_id)
                    messages.append(f"Added {self.card_name(card_id)}.")
            elif action == "remove_card":
                card_id = result.get("card")
                if card_id in state.deck_ids:
                    state.deck_ids.remove(card_id)
                    messages.append(f"Removed {self.card_name(card_id)}.")
            elif action == "upgrade_card":
                from_card = result.get("from")
                to_card = result.get("to")
                if from_card in state.deck_ids and to_card in self.cards:
                    state.deck_ids.remove(from_card)
                    state.deck_ids.append(to_card)
                    messages.append(f"{self.card_name(from_card)} became {self.card_name(to_card)}.")
            elif action == "add_relic":
                relic_id = result.get("relic")
                if relic_id in self.relics and relic_id not in state.relic_ids:
                    state.relic_ids.append(relic_id)
                    messages.append(f"Gained relic: {self.relic_name(relic_id)}.")
            elif action == "set_flag":
                flag = result.get("flag")
                if flag:
                    state.event_flags.add(flag)
        return messages

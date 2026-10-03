from random import sample

from ...adventure import AdventureData, AdventureNode, AdventureState
from ...game_state import Game
from ...keyboard import KEY_DOWN, KEY_ENTER, KEY_ESC, KEY_LEFT, KEY_RIGHT, KEY_UP, get_key
from ..game.game_controller import GameController
from ..game.game_view import GameView
from .adventure_view import AdventureView


class AdventureController:
    CARD_PRICE = 18
    RELIC_PRICE = 35
    REMOVE_PRICE = 25
    REST_HEAL = 14

    def __init__(self, player_id: str, adventure_id: str = "default"):
        self.data = AdventureData()
        self.state = self.data.create_state(player_id, adventure_id)
        self.view = AdventureView(self.data)
        self.selected_index = 0

    def run(self) -> str:
        while not self.state.is_complete and self.state.current_hp > 0:
            node = self._choose_node()
            if node is None:
                return "main_menu"
            result = self._handle_node(node)
            if result == "main_menu":
                return "main_menu"
            if result == "defeat":
                self.view.display_message(
                    "Adventure Failed",
                    ["You were defeated before reaching the end of the route."],
                    self.state,
                )
                get_key()
                return "main_menu"
            if result == "victory":
                self.state.visited_nodes.append(node)
                self.view.display_message(
                    "Adventure Complete",
                    ["The Overseer falls. Your route through Neon Ascent is complete."],
                    self.state,
                )
                get_key()
                return "main_menu"
            self.state.visited_nodes.append(node)
            self.state.advance()
            self.selected_index = 0

        return "main_menu"

    def _choose_node(self) -> AdventureNode | None:
        self.selected_index = min(self.selected_index, max(0, len(self.state.current_nodes) - 1))
        while True:
            self.view.display_map(self.state, self.selected_index)
            key = get_key()
            if key in (KEY_UP, KEY_LEFT):
                self.selected_index = (self.selected_index - 1) % len(self.state.current_nodes)
            elif key in (KEY_DOWN, KEY_RIGHT):
                self.selected_index = (self.selected_index + 1) % len(self.state.current_nodes)
            elif key == KEY_ENTER:
                return self.state.current_nodes[self.selected_index]
            elif key == KEY_ESC:
                return None

    def _select_option(
        self,
        title: str,
        body: str,
        options: list[str],
        allow_escape: bool = False,
    ) -> int | None:
        if not options:
            return None
        selected = 0
        while True:
            self.view.display_options(title, body, options, selected, self.state)
            key = get_key()
            if key in (KEY_UP, KEY_LEFT):
                selected = (selected - 1) % len(options)
            elif key in (KEY_DOWN, KEY_RIGHT):
                selected = (selected + 1) % len(options)
            elif key == KEY_ENTER:
                return selected
            elif key == KEY_ESC and allow_escape:
                return None

    def _handle_node(self, node: AdventureNode) -> str:
        if node.type in {"Battle", "Elite", "Boss"}:
            return self._handle_battle(node)
        if node.type == "Event":
            self._handle_event(node)
            return "continue"
        if node.type == "Shop":
            self._handle_shop()
            return "continue"
        if node.type == "Rest":
            self._handle_rest()
            return "continue"
        self.view.display_message("Unknown Node", [f"Nothing happens at {node.label}."], self.state)
        get_key()
        return "continue"

    def _handle_battle(self, node: AdventureNode) -> str:
        if not node.enemy:
            self.view.display_message("Missing Enemy", [f"{node.label} has no enemy configured."], self.state)
            get_key()
            return "continue"

        game = Game(
            player_id=self.state.player_id,
            enemy_id=node.enemy,
            player_deck_ids=self.state.deck_ids,
            player_hp=self.state.current_hp,
            player_max_hp=self.state.max_hp,
            player_base_mana=self.state.base_mana,
            battle_modifiers=self.data.battle_modifiers(self.state),
        )
        controller = GameController(game, GameView())
        result = controller.run()
        if result == "main_menu":
            return "main_menu"
        if result == "defeat":
            self.state.current_hp = max(0, game.player.hp if game.player else 0)
            return "defeat"

        messages = self._sync_after_battle(game)
        self.state.defeated_enemies.append(node.enemy)
        messages.insert(0, f"Won {node.gold} Gold from {node.label}.")
        self.state.gold += node.gold
        messages.extend(self.data.apply_after_battle_relics(self.state))

        if node.relic:
            relic_id = self.data.random_relic(self.state)
            if relic_id:
                self.state.relic_ids.append(relic_id)
                messages.append(
                    f"Gained relic: {self.data.relic_name(relic_id)} - "
                    f"{self.data.relic_description(relic_id)}"
                )

        self.view.display_message("Victory", messages, self.state)
        get_key()

        if node.type == "Boss":
            return "victory"

        self._choose_card_reward()
        return "continue"

    def _sync_after_battle(self, game: Game) -> list[str]:
        if not game.player:
            return []
        messages = []
        previous_base_mana = self.state.base_mana
        self.state.current_hp = max(1, game.player.hp)
        relic_mana_bonus = self.data.battle_modifiers(self.state).get("max_mana_bonus", 0)
        self.state.base_mana = max(0, game.player.max_mana - relic_mana_bonus)
        if self.state.base_mana != previous_base_mana:
            messages.append(f"Max Mana is now {self.state.base_mana}.")
        all_cards = list(game.player.deck) + list(game.player.hand) + list(game.player.discard_pile)
        self.state.deck_ids = [card.id for card in all_cards]
        return messages

    def _choose_card_reward(self):
        reward_ids = self.data.card_reward_options(self.state)
        options = [f"Add {self.data.card_name(card_id)}" for card_id in reward_ids]
        options.append("Skip reward")
        index = self._select_option("Card Reward", "Choose one card to add to your deck.", options)
        if index is not None and index < len(reward_ids):
            card_id = reward_ids[index]
            self.state.deck_ids.append(card_id)
            self.view.display_message("Card Added", [f"Added {self.data.card_name(card_id)}."], self.state)
            get_key()

    def _handle_event(self, node: AdventureNode):
        event = self.data.events.get(node.event or "")
        if not event:
            self.view.display_message("Quiet Road", ["The event data is missing, so nothing happens."], self.state)
            get_key()
            return
        options = [option.get("label", "Option") for option in event.get("options", [])]
        while True:
            index = self._select_option(event.get("title", node.label), event.get("text", ""), options, allow_escape=True)
            if index is None:
                return
            selected = event.get("options", [])[index]
            results = selected.get("results", [])
            error = self.data.event_choice_error(self.state, results)
            messages = [error] if error else self.data.apply_event_results(self.state, results)
            self.view.display_message(event.get("title", node.label), messages or ["Nothing changes."], self.state)
            get_key()
            if not error:
                return

    def _handle_shop(self):
        shop_pool = [card_id for card_id in self.state.shop_card_pool if card_id in self.data.cards]
        shop_cards = sample(shop_pool, min(3, len(shop_pool))) if shop_pool else []
        while True:
            removable = self._first_removable_card()
            available_relics = self.data.available_relics(self.state)
            card_price = self._shop_price(self.CARD_PRICE)
            remove_price = self._shop_price(self.REMOVE_PRICE)
            relic_price = self._shop_price(self.RELIC_PRICE)
            options = [f"Buy {self.data.card_name(card_id)} ({card_price} Gold)" for card_id in shop_cards]
            if removable:
                options.append(f"Thin deck: remove {self.data.card_name(removable)} ({remove_price} Gold)")
            if available_relics:
                relic_id = available_relics[0]
                options.append(f"Buy {self.data.relic_name(relic_id)} ({relic_price} Gold)")
            options.append("Leave shop")

            index = self._select_option(
                "Night Market",
                "Spend Gold to buy tools or thin weak starter cards so stronger cards appear more often.",
                options,
                allow_escape=True,
            )
            if index is None or index == len(options) - 1:
                return

            card_count = len(shop_cards)
            if index < card_count:
                self._buy_card(shop_cards[index])
            elif removable and index == card_count:
                self._remove_card(removable)
            else:
                self._buy_relic(available_relics[0])

    def _buy_card(self, card_id: str):
        price = self._shop_price(self.CARD_PRICE)
        if self.state.gold < price:
            self._show_shop_message("Not enough Gold.")
            return
        self.state.gold -= price
        self.state.deck_ids.append(card_id)
        self._show_shop_message(f"Bought {self.data.card_name(card_id)}.")

    def _remove_card(self, card_id: str):
        price = self._shop_price(self.REMOVE_PRICE)
        if self.state.gold < price:
            self._show_shop_message("Not enough Gold.")
            return
        self.state.gold -= price
        self.state.deck_ids.remove(card_id)
        self._show_shop_message(f"Removed {self.data.card_name(card_id)}.")

    def _buy_relic(self, relic_id: str):
        price = self._shop_price(self.RELIC_PRICE)
        if self.state.gold < price:
            self._show_shop_message("Not enough Gold.")
            return
        self.state.gold -= price
        self.state.relic_ids.append(relic_id)
        self._show_shop_message(
            f"Bought {self.data.relic_name(relic_id)}: {self.data.relic_description(relic_id)}"
        )

    def _show_shop_message(self, message: str):
        self.view.display_message("Night Market", [message], self.state)
        get_key()

    def _first_removable_card(self) -> str | None:
        for card_id in ("strike", "defend", "pierce"):
            if card_id in self.state.deck_ids:
                return card_id
        return self.state.deck_ids[0] if self.state.deck_ids else None

    def _handle_rest(self):
        train_target = self._train_target()
        heal_amount = self._rest_heal_amount()
        options = [f"Recover {heal_amount} HP"]
        if train_target:
            old_card, new_card = train_target
            options.append(f"Train {self.data.card_name(old_card)} into {self.data.card_name(new_card)}")
        options.append("Move on")
        index = self._select_option(
            "Rest Station",
            "Patch your wounds or tune one basic card into a stronger version.",
            options,
        )
        if index == 0:
            before = self.state.current_hp
            self.state.current_hp = min(self.state.max_hp, self.state.current_hp + heal_amount)
            self.view.display_message(
                "Rested",
                [f"Recovered {self.state.current_hp - before} HP."],
                self.state,
            )
            get_key()
        elif train_target and index == 1:
            old_card, new_card = train_target
            self.state.deck_ids.remove(old_card)
            self.state.deck_ids.append(new_card)
            self.view.display_message(
                "Trained",
                [f"{self.data.card_name(old_card)} became {self.data.card_name(new_card)}."],
                self.state,
            )
            get_key()

    def _train_target(self) -> tuple[str, str] | None:
        if "strike" in self.state.deck_ids:
            return "strike", "double_strike"
        if "defend" in self.state.deck_ids:
            return "defend", "full_defend"
        return None

    def _relic_bonus(self, action: str) -> int:
        total = 0
        for relic_id in self.state.relic_ids:
            for effect in self.data.relics.get(relic_id, {}).get("effects", []):
                if effect.get("action") == action:
                    total += int(effect.get("value", 0))
        return total

    def _shop_price(self, base_price: int) -> int:
        return max(0, base_price - self._relic_bonus("shop_discount"))

    def _rest_heal_amount(self) -> int:
        return self.REST_HEAL + self._relic_bonus("rest_heal_bonus")

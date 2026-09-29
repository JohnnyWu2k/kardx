from __future__ import annotations

from dataclasses import dataclass
from contextlib import nullcontext

from kardx.game_state import Game
from kardx.scenes.game.game_controller import GameController
from kardx.scenes.game.game_view import GameView
from kardx.keyboard import use_key_reader
from kardx.view_utils import use_terminal


@dataclass
class CardBattleResult:
    victory: bool
    hp: int
    max_hp: int
    base_mana: int
    deck_ids: list[str]


def run_card_battle(
    enemy_id: str,
    player_id: str = "player_balanced",
    deck_ids: list[str] | None = None,
    hp: int | None = None,
    max_hp: int | None = None,
    base_mana: int | None = None,
    terminal=None,
) -> CardBattleResult:
    game = Game(
        player_id=player_id,
        enemy_id=enemy_id,
        player_deck_ids=deck_ids,
        player_hp=hp,
        player_max_hp=max_hp,
        player_base_mana=base_mana,
    )
    controller = GameController(game, GameView())
    with (use_terminal(terminal) if terminal is not None else nullcontext()), (
        use_key_reader(terminal.get_key, terminal.get_key_non_blocking)
        if terminal is not None else nullcontext()
    ):
        result = controller.run()
    player = game.player
    if not player:
        return CardBattleResult(False, 0, 0, 0, [])

    all_cards = list(player.deck) + list(player.hand) + list(player.discard_pile)
    return CardBattleResult(
        victory=result == "victory",
        hp=max(0, player.hp),
        max_hp=player.max_hp,
        base_mana=player.max_mana,
        deck_ids=[card.id for card in all_cards],
    )

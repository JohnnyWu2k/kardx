"""Battle and progression regressions that are independent of terminal input."""

from collections import Counter
from unittest.mock import patch

import pytest

from kardx.adventure import AdventureData
from kardx.scenes.adventure.adventure_controller import AdventureController
from kardx.scenes.adventure.adventure_view import AdventureView
from kardx.game_state import Game
from kardx.loader import load_packaged_json5_data
from kardx.player import Player
from kardx.sandbox import SandboxGame


@pytest.fixture
def battle():
    with patch("kardx.game_state.load_game_data", side_effect=load_packaged_json5_data):
        game = Game("player_balanced", "enemy_giant_rat")
    game.start_battle()
    game.start_player_turn()
    return game


@pytest.mark.parametrize("actor", ["player", "enemy"])
def test_self_damage_ends_battle_for_either_actor(battle, actor):
    source = getattr(battle, actor)
    source.hp = 1
    source.mana = 4
    source.hand = [battle.all_cards["glass_cannon"]]
    if actor == "player":
        battle.play_card(0)
    else:
        battle.play_enemy_card(source.hand[0])
    assert source.hp == 0
    assert not battle.is_running


def test_mutual_lethal_card_resolves_as_defeat(battle):
    battle.player.hp = battle.enemy.hp = 1
    battle.player.mana = 4
    battle.player.hand = [battle.all_cards["glass_cannon"]]
    battle.play_card(0)
    assert battle.player.hp == battle.enemy.hp == 0
    assert not battle.is_running


def test_dead_player_cannot_restart_battle(battle):
    battle.player.set_hp(0)
    battle.start_battle()
    assert not battle.is_running


def test_finished_battle_rejects_card_plays(battle):
    battle.is_running = False
    hp, mana = battle.enemy.hp, battle.player.mana
    assert battle.play_card(0)[0] != "success"
    assert (battle.enemy.hp, battle.player.mana) == (hp, mana)


def test_enemy_cannot_play_unowned_or_unaffordable_cards(battle):
    battle.enemy.mana = 0
    card = battle.all_cards["glass_cannon"]
    before = battle.player.hp
    assert battle.play_enemy_card(card) == []
    assert battle.enemy.mana == 0
    assert battle.player.hp == before


def test_max_mana_reduction_caps_available_mana():
    player = Player("test", 10, 3, [])
    player.mana = 3
    player.add_max_mana(-1)
    assert player.mana == player.max_mana == 2


def test_damage_and_defense_never_create_negative_resources():
    player = Player("test", 10, 3, [])
    player.add_def(-5)
    assert player.defend == 0
    assert player.take_damage(-3) == {"dealt": 0, "blocked": 0}
    assert player.hp == 10
    player.take_damage(30)
    assert player.hp == 0


def test_play_discard_and_reshuffle_preserve_every_card(battle):
    player = battle.player
    count = lambda: Counter(card.id for card in player.deck + player.hand + player.discard_pile)
    before = count()
    for _ in range(25):
        while player.hand:
            battle.discard_player_card(0)
        player.start_turn()
    assert count() == before


def test_first_attack_relic_also_applies_to_true_damage_once(battle):
    battle.battle_modifiers["first_attack_damage_bonus"] = 2
    battle.player.hand = [battle.all_cards["pierce"], battle.all_cards["strike"]]
    before = battle.enemy.hp
    battle.play_card(0)
    assert before - battle.enemy.hp == 6
    before = battle.enemy.hp
    battle.play_card(0)
    assert before - battle.enemy.hp == 6


@pytest.fixture
def sandbox():
    with patch("kardx.sandbox.load_game_data", side_effect=load_packaged_json5_data):
        game = SandboxGame()
        game.start("player_balanced")
    return game


def test_unavailable_upgrade_preserves_materials_and_turn(sandbox):
    sandbox.state.deck_ids = ["defend"]
    sandbox.state.inventory = {"wood": 1, "stone": 1}
    before = sandbox.state.to_dict()
    messages = sandbox.craft("double_strike")
    assert "No Strike" in " ".join(messages)
    assert sandbox.state.to_dict() == before


def test_explicit_zero_item_reward_is_a_noop(sandbox):
    sandbox.apply_effects([{"action": "add_item", "item": "wood", "value": 0}])
    assert "wood" not in sandbox.state.inventory


def test_negative_recipe_cost_cannot_generate_materials(sandbox):
    sandbox.data.recipes["double_strike"]["requires"] = {"wood": -1}
    previous = sandbox.state.to_dict()
    assert "invalid" in " ".join(sandbox.craft("double_strike"))
    assert sandbox.state.to_dict() == previous


def test_talking_cannot_restart_a_completed_quest(sandbox):
    sandbox.state.quests["Explore the Old Well"] = "complete"
    sandbox.state.current_room = "city_hall"
    sandbox.talk("mayor")
    assert sandbox.state.quests["Explore the Old Well"] == "complete"


def test_data_driven_locked_exit_uses_its_required_item(sandbox):
    sandbox.data.rooms["cellar"]["locked_exits"] = {
        "east": {"requires_item": "rusty_key"}
    }
    sandbox.state.add_item("rusty_key")
    sandbox.use("rusty_key")
    sandbox.go("east")
    assert sandbox.state.current_room == "storage"


def test_encounter_validation_checks_retreat_rooms(sandbox):
    sandbox.data.encounters["rat_passage"]["retreat_room"] = "missing_room"
    assert any("missing_room" in error for error in sandbox.data.validate())


@pytest.fixture
def adventure():
    with patch("kardx.adventure.load_game_data", side_effect=load_packaged_json5_data):
        return AdventureData()


def test_event_cost_is_paid_before_any_rewards(adventure):
    state = adventure.create_state("player_balanced")
    state.gold = 0
    state.current_hp = 1
    results = adventure.events["field_medic"]["options"][0]["results"]
    messages = adventure.apply_event_results(state, results)
    assert state.current_hp == 1
    assert state.gold == 0
    assert "paid_medic" not in state.event_flags
    assert "Gold" in " ".join(messages)


def test_unaffordable_event_choice_can_be_retried(adventure):
    from kardx.adventure import AdventureNode
    from unittest.mock import Mock

    controller = AdventureController.__new__(AdventureController)
    controller.data = adventure
    controller.state = adventure.create_state("player_balanced")
    controller.state.gold = 0
    controller.view = Mock(spec=AdventureView)
    controller._select_option = Mock(side_effect=[0, 1])
    with patch("kardx.scenes.adventure.adventure_controller.get_key"):
        controller._handle_event(AdventureNode("medic", "Event", "Medic", event="field_medic"))
    assert controller._select_option.call_count == 2
    assert "paid_medic" not in controller.state.event_flags
    assert "full_defend" in controller.state.deck_ids


def test_empty_generated_route_is_rejected(adventure):
    definition = adventure.adventures["default"]
    definition["map_template"] = [["Battle"]]
    definition["node_pools"] = {"Event": []}
    with pytest.raises(ValueError, match="route|row|pool"):
        adventure.create_state("player_balanced")

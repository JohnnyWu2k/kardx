import curses
from unittest.mock import patch

import pytest

from kardx.settings import Settings
from kardx.view_utils import use_terminal
from kardx.scenes.game.game_view import GameView
from ttx.art import card_pixels, atlas_region
from ttx.combat.card_battle import prepare_card_battle
from ttx.terminal import Frame, TerminalRenderer
from ttx.world.camera import Camera
from test_mouse_experience import Screen


def test_centered_hand_targets_and_art_on_large_terminal():
    game = prepare_card_battle("enemy_giant_rat")
    game.start_battle()
    game.start_player_turn()
    from ttx.terminal import CardTerminal
    terminal = CardTerminal(TerminalRenderer(Screen(54, 210)))
    terminal.first_frame = False
    with patch.object(curses, "color_pair", return_value=0), use_terminal(terminal):
        GameView().display_board(game.player, game.enemy, game.action_log, selected_index=0)
    targets = [t for t in terminal.mouse_targets if isinstance(t[-1], tuple)]
    assert targets[0][1] >= 54 // 2
    assert abs(targets[0][0] - (210 - targets[-1][2])) <= 1
    assert targets[0][3] - targets[0][1] >= 12
    assert any("\033[3" in line and "▀" in line for line in terminal.lines)


def test_png_regions_and_pixel_colors_are_distinct():
    arts = [card_pixels(name, 20, 8) for name in ("attack", "defend", "heal", "mana", "fire", "ice")]
    assert len(set(arts)) == 6
    assert atlas_region("dirt").tobytes() != atlas_region("stone").tobytes()
    frame = Frame(1, 2)
    with patch.object(curses, "color_pair", side_effect=lambda i: i * 256), patch.object(curses, "A_COLOR", 0xff00):
        frame.addstr(0, 0, "\033[31;44m▀\033[0mX")
    assert frame.cells[0][0] == ("▀", (16 + 1 * 8 + 4) * 256)
    assert frame.cells[0][1] == ("X", 0)


def test_transition_settings_round_trip_and_validation(tmp_path):
    path = tmp_path / "settings.jsonc"
    settings = Settings(path)
    settings.set("battle_particle_color", "cyan")
    settings.set("battle_particle_speed", 2.0)
    settings.set("battle_transition_duration", 1.5)
    loaded = Settings(path)
    assert loaded.get("battle_particle_color") == "cyan"
    assert loaded.get("battle_particle_speed") == 2.0
    assert loaded.get("battle_transition_duration") == 1.5
    settings.set("battle_particle_speed", float("nan"))
    settings.set("battle_transition_duration", -100)
    settings.set("battle_particle_color", [])
    assert settings.get("battle_particle_speed") == 1
    assert settings.get("battle_transition_duration") == 0
    assert settings.get("battle_particle_color") == "magenta"


def test_settings_menu_saves_all_controls_and_previews(tmp_path):
    from ttx.cli import settings_menu
    settings = Settings(tmp_path / "settings.jsonc")
    renderer = TerminalRenderer(Screen())
    renderer.last = renderer.frame()
    with patch("kardx.settings.settings_manager", settings), patch("ttx.cli._menu", side_effect=[1, 2, 3, 4]), patch.object(
        renderer, "begin_battle_transition"
    ) as begin, patch.object(renderer, "complete_battle_transition") as complete:
        settings_menu(renderer.screen, renderer)
    loaded = Settings(settings.path)
    assert loaded.get("battle_particle_color") == "cyan"
    assert loaded.get("battle_transition_duration") == 1.0
    begin.assert_called_once()
    complete.assert_called_once()


def test_duration_covers_both_animation_phases():
    from kardx.settings import settings_manager
    renderer = TerminalRenderer(Screen())
    clock = [0.0]
    def sleep(seconds):
        clock[0] += seconds
    with patch.dict(settings_manager.data, battle_transition_duration=1.5), patch.object(
        curses, "color_pair", return_value=0
    ), patch("ttx.terminal.time.monotonic", side_effect=lambda: clock[0]), patch("ttx.terminal.time.sleep", side_effect=sleep):
        renderer.begin_battle_transition()
        renderer.complete_battle_transition(renderer.frame())
    assert clock[0] == pytest.approx(1.5)


def test_particle_color_and_speed_change_veil_and_zero_duration_skips_animation():
    from kardx.settings import settings_manager
    renderer = TerminalRenderer(Screen(30, 80))
    base = renderer.frame()
    with patch.object(curses, "color_pair", side_effect=lambda i: i * 256), patch.object(curses, "A_COLOR", 0xff00), patch.dict(
        settings_manager.data, battle_particle_color="cyan", battle_particle_speed=1.0,
        battle_transition_duration=0.0,
    ):
        first = renderer._battle_veil(base, 1, 3)
        assert all(attr & curses.A_COLOR == 4 * 256 for row in first.cells for _, attr in row)
        with patch.dict(settings_manager.data, battle_particle_speed=4.0):
            assert first.cells == renderer._battle_veil(base, 1, 3).cells
        with patch("ttx.terminal.time.sleep") as sleep:
            renderer.begin_battle_transition()
            renderer.complete_battle_transition(base)
            sleep.assert_not_called()
            assert renderer.last.cells == base.cells


@pytest.mark.parametrize("visible", [(40, 30), (3, 3), (1000, 1000)])
def test_camera_keeps_player_visible_after_resize_and_teleport(visible):
    camera = Camera()
    for player in ((100, 21), (511, 191), (0, 0), (250, 100)):
        origin = camera.follow(player, visible, (512, 192))
        assert all(start <= p < start + size for start, p, size in zip(origin, player, visible))

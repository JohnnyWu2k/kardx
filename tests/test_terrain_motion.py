"""Visible terrain, pose and four-direction page-switching regressions."""
import curses
from unittest.mock import patch

import pytest

from ttx.terminal import Frame
from ttx.world.animation import ActorAnimation
from ttx.world.camera import Camera
from ttx.world import materials
from ttx.world.materials import MATERIALS, PALETTE, QUADRANTS, material_pixels
from ttx.world.render import DotCanvas, actor_sprite, terrain, _pair_number


class RockMap:
    AIR = "."

    def get_tile(self, x, y):
        return "#"


def test_packaged_materials_are_opaque_distinct_and_keep_ore_colors():
    textures = {name: material_pixels(name) for name in MATERIALS}
    assert len(set(textures.values())) == 8
    for texture in textures.values():
        assert len(texture) == 16
        assert all(len(row) == 16 and all(0 <= color < len(PALETTE) for color in row) for row in texture)
    for name, accents in (("iron", {6, 7}), ("lead", {10}), ("crystal", {11}), ("coal", {0})):
        assert any(color in accents for row in textures[name] for color in row)


def test_opaque_quadrants_remove_dim_shadows_and_keep_mining_holes():
    canvas = DotCanvas(4, 8)
    terrain(canvas, RockMap(), (0, 0), {"0,0": {"char": "."}}, {})
    frame = Frame(4, 8)
    with patch.object(curses, "color_pair", side_effect=lambda i: i << 8), patch.object(
        materials, "_extended_pairs", True
    ):
        canvas.paint(frame)
    assert all(char in QUADRANTS for row in frame.cells for char, _ in row)
    assert all(frame.cells[y][x] == (" ", 0) for y in range(2) for x in range(4))
    assert all(attr and not attr & curses.A_DIM for row in frame.cells[2:] for _, attr in row)


def test_vertical_subtile_scroll_preserves_world_anchored_material_samples():
    before, after = DotCanvas(6, 12), DotCanvas(6, 12)
    terrain(before, RockMap(), (0, 0), {}, {})
    terrain(after, RockMap(), (0, 0.125), {}, {})
    def pixel(canvas, x, y):
        return canvas.pixels[y // 4][x // 2][y % 4 * 2 + x % 2]
    assert all(pixel(before, x, y + 1) == pixel(after, x, y) for y in range(23) for x in range(24))


def test_material_pairs_fit_windows_limit_and_have_eight_color_fallback():
    with patch.object(curses, "COLORS", 256, create=True), patch.object(
        curses, "COLOR_PAIRS", 256, create=True
    ), patch.object(curses, "init_pair") as init, patch.object(materials, "_extended_pairs", False):
        materials.init_material_colors()
        assert materials._extended_pairs
        assert len(init.call_args_list) == 169
        assert max(call.args[0] for call in init.call_args_list) == 248
    with patch.object(curses, "COLOR_PAIRS", 128, create=True), patch.object(
        curses, "init_pair"
    ) as init, patch.object(curses, "color_pair", side_effect=lambda i: i), patch.object(materials, "_extended_pairs", True):
        materials.init_material_colors()
        assert not materials._extended_pairs
        assert 16 <= materials.material_attr(11, 2) < 80
        init.assert_not_called()
    with patch.object(curses, "A_COLOR", -0x1000000):
        assert _pair_number(-134217728) == 248


@pytest.mark.parametrize("axis,direction", [(0, 1), (0, -1), (1, 1), (1, -1)])
def test_all_camera_edges_switch_immediately_without_intermediate_frames(axis, direction):
    camera = Camera()
    visible, world = (40, 30), (512, 192)
    start = camera.follow((100, 90), visible, world, now=0)
    player = [100, 90]
    player[axis] = start[axis] + (visible[axis] - 1 if direction > 0 else 0.9)
    target = camera.follow(player, visible, world, now=1)
    assert target == camera.position == camera.display_position
    assert direction * (target[axis] - start[axis]) > 0
    samples = [camera.follow(player, visible, world, now=1 + step / 60) for step in range(1, 30)]
    assert all(sample == target for sample in samples)
    player[axis] -= direction * .25  # A small reversal must not flip back.
    assert all(camera.follow(player, visible, world, now=2 + step / 60) == target for step in range(10))


def test_fast_fall_resize_and_teleport_keep_actor_visible():
    camera = Camera()
    camera.follow((100, 90), (40, 30), (512, 192), now=0)
    for step in range(80):
        player = (100, min(191, 103 + step * 0.66))
        start = camera.follow(player, (40, 30), (512, 192), now=1 + step / 60)
        assert all(s <= p < s + size for s, p, size in zip(start, player, (40, 30)))
    for player, visible in (((0, 0), (40, 30)), ((511, 191), (40, 30)), ((100, 90), (1, 1))):
        start = camera.follow(player, visible, (512, 192), now=3)
        assert all(s <= p < s + size for s, p, size in zip(start, player, visible))
    tiny_target = camera.position
    for step in range(10):
        camera.follow((100, 90), (1, 1), (512, 192), now=4 + step / 60)
        assert camera.position == tiny_target


def test_pose_cycle_tracks_distance_not_render_rate_and_holds_between_ticks():
    def walk(frames):
        animation = ActorAnimation()
        return [animation.sample({"x": 10 + 2 * step / frames, "y": 20, "vx": 0.1, "grounded": True}, step / frames)
                for step in range(frames + 1)][-1]
    assert walk(30)["walk_frame"] == walk(60)["walk_frame"] == walk(120)["walk_frame"]
    animation = ActorAnimation()
    actor = {"x": 10, "y": 20, "vx": 0.2, "grounded": True, "facing": -1}
    first = animation.sample(actor, 0)
    second = animation.sample(actor, 0.001)
    assert first == second
    assert "pose" not in actor
    assert second["pose"] == "walk" and second["facing"] == -1


def test_jump_fall_landing_pause_and_teleport_poses():
    animation = ActorAnimation()
    actor = {"x": 10, "y": 10, "grounded": False, "vy": -0.5}
    assert animation.sample(actor, 0)["pose"] == "rise"
    actor.update(vy=0.5)
    assert animation.sample(actor, 0.1)["pose"] == "fall"
    assert animation.sample(actor, 0.2, frozen=True)["pose"] == "fall"
    actor.update(grounded=True, vy=0)
    assert animation.sample(actor, 0.3)["pose"] == "land"
    assert animation.sample(actor, 0.5)["pose"] == "idle"
    actor.update(x=100)
    assert animation.sample(actor, 0.6)["pose"] == "idle"


def test_actor_silhouettes_have_distinct_poses_and_mirror_facing():
    views = []
    for pose in ("idle", "walk", "rise", "fall", "land"):
        canvas = DotCanvas(4, 12)
        actor_sprite(canvas, {"x": 1, "y": 1, "pose": pose, "walk_frame": 0}, (0, 0), 0)
        views.append(tuple(tuple(row) for row in canvas.pixels))
    assert len(set(views)) == 5
    left, right = DotCanvas(4, 12), DotCanvas(4, 12)
    actor_sprite(left, {"x": 1, "y": 1, "facing": -1}, (0, 0), 0)
    actor_sprite(right, {"x": 1, "y": 1, "facing": 1}, (0, 0), 0)
    assert left.pixels != right.pixels

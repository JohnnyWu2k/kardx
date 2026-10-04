"""Export a deterministic motion preview and report CPU frame composition cost."""
import curses
import json
import statistics
import time
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw
from preview_world import make_game, frame_image
from ttx.world.animation import ActorAnimation
from ttx.world.camera import Camera
from ttx.world.materials import PALETTE
from ttx.world.render import DotCanvas, actor_sprite
from ttx.terminal import Frame


def main():
    output = Path("dist")
    output.mkdir(exist_ok=True)
    with patch.object(curses, "color_pair", new=lambda i: i << 8), patch.object(
        curses, "A_COLOR", 0xff00
    ), patch("ttx.world.materials._extended_pairs", True):
        game, state = make_game()
        game.stdscr.getmaxyx = lambda: (50, 210)
        state["objects"] = {}
        player = state["players"]["p"]
        player.update(x=100, y=65)
        game._compose_frame()
        timings = {}
        for scenario in ("stationary", "continuous_scroll_baseline"):
            samples = []
            for step in range(90):
                if scenario == "continuous_scroll_baseline":
                    game._camera_offset = lambda step=step: (80 + step / 8, 54 + step / 8)
                started = time.perf_counter()
                game._compose_frame()
                samples.append((time.perf_counter() - started) * 1000)
            timings[scenario] = {"median_ms": round(statistics.median(samples), 2),
                                 "p95_ms": round(sorted(samples)[int(len(samples) * .95)], 2)}
        (output / "render-timings.json").write_text(json.dumps(timings, indent=2), encoding="utf-8")
        print(json.dumps(timings))

        # Show a direct page change on every edge, at the actual frame clock.
        demos = []
        for axis, direction, title in ((0, 1, "RIGHT"), (0, -1, "LEFT"), (1, 1, "DOWN"), (1, -1, "UP")):
            demo, world = make_game()
            demo.stdscr.getmaxyx = lambda: (20, 84)
            world["objects"] = {}
            world["custom_tiles"] = {f"{x},{y}": {"char": "."} for y in range(62, 66) for x in range(50, 151)}
            world["custom_tiles"].update({f"{x},{y}": {"char": "."} for y in range(30, 121) for x in range(99, 102)})
            world["terrain_revision"] = 1
            actor = world["players"]["p"]
            actor.update(x=100, y=65, grounded=axis == 0, vx=direction * .42 if axis == 0 else 0,
                         vy=direction * .5 if axis == 1 else 0)
            demo._camera = Camera()
            origin = demo._camera.follow((100, 65), (15.5, 10), (512, 192), now=0)
            actor["x" if axis == 0 else "y"] = origin[axis] + ((15.5, 10)[axis] - 1.3 if direction > 0 else 1.3)
            animation = ActorAnimation()
            demos.append((demo, world, actor, axis, direction, title, animation))
        images = []
        for step in range(45):
            now = step / 60
            sheet = Image.new("RGB", (1008, 440), PALETTE[0])
            draw = ImageDraw.Draw(sheet)
            for index, (demo, world, actor, axis, direction, title, animation) in enumerate(demos):
                actor["x" if axis == 0 else "y"] += direction * .06
                world["players"]["p"] = animation.sample(actor, now)
                with patch("ttx.net.client.time.monotonic", return_value=now):
                    frame = demo._compose_frame()
                x, y = index % 2 * 504, index // 2 * 220
                sheet.paste(frame_image(frame, cw=6, ch=10), (x, y + 20))
                draw.text((x + 8, y + 4), title, fill="#dae5ee")
            images.append(sheet)
        images[0].save(output / "camera-motion.gif", save_all=True, append_images=images[1:],
                       duration=[20, 10, 20] * 15, loop=0)
        contact = Image.new("RGB", (1008, 440 * 3), PALETTE[0])
        for index, step in enumerate((0, 13, 30)):
            contact.paste(images[step], (0, index * 440))
        contact.save(output / "camera-motion-frames.png")

        frames = []
        for step in range(40):
            canvas = DotCanvas(4, 40)
            for index, pose in enumerate(("idle", "walk", "rise", "fall", "land")):
                actor_sprite(canvas, {"x": index * 2, "y": 0, "pose": pose,
                                      "facing": 1, "walk_frame": step // 2 % 8}, (0, 0), 0)
            frame = Frame(4, 40)
            canvas.paint(frame)
            picture = frame_image(frame, cw=16, ch=32)
            ImageDraw.Draw(picture).text((8, 96), "IDLE          WALK          RISE          FALL          LAND", fill="#dae5ee")
            frames.append(picture)
        frames[0].save(output / "actor-motion.gif", save_all=True, append_images=frames[1:], duration=50, loop=0)
        frames[3].save(output / "actor-poses.png")


if __name__ == "__main__":
    main()

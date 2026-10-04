# Pixel assets

`fantasy_atlas.png` was generated using the built-in ImageGen tool on 2026-10-03.
The runtime crops a 4-column × 2-row grid: attack, defend, heal, mana / fire, ice,
dirt, stone. Keep the complete atlas in the package; no external image path is
required. Original image dimensions are read at runtime.

Card art uses nearest-neighbor sampling and an eight-color terminal palette.
Each `▀` card cell contains two independently colored vertical pixels.
The dirt/stone regions in this older atlas are retained for compatibility;
world terrain now uses the separate material atlas described below.
Tree alpha coverage preserves thin roots while its RGB samples use
nearest-neighbor sampling.

Generation prompt:

> Create one production game asset atlas, square 1024x1024, exactly 4 columns and 2 rows of equal size cells with no gutters, no text, no borders. This is a terminal fantasy pixel-art card game, strong large silhouettes that remain recognizable downscaled. Every cell uses crisp chunky pixel art, a limited vivid 16-color palette, no antialiasing or gradients. Each cell has an opaque very dark navy background. Top row left to right: 1 a brilliant silver diagonal sword with cyan magical arc, 2 a heavy blue silver shield with golden rune, 3 a glowing emerald healing potion with leaf sparks, 4 a violet magical mana crystal with orbiting gold sparks. Bottom row left to right: 1 a fierce orange fireball with red flame tongues, 2 an icy cyan snowflake crystal with frost shards, 3 seamless earthy brown dirt texture with pebbles (fills entire cell edge to edge), 4 seamless dark slate stone texture with angular gray cracks (fills entire cell edge to edge). The six card subjects are each centered inside their own cell with 15 percent padding and high contrast. No letters, labels, watermark, card frames, UI, or extraneous objects.

The generated atlas is 1254×1254; runtime cropping uses proportional boundaries.
Existing `woodland_tree.png` and `grass_road.png` remain the tree and path assets.

## Terrain materials (2026-10-04)

`terrain_atlas.png` is the full generated master, made with the built-in ImageGen
tool using the user's dirt, gray stone and orange iron-ore references as style
guidance. The exact final prompt is saved in `terrain_prompt.txt`.

The 4-column × 2-row atlas contains:

| Row | Column 1 | Column 2 | Column 3 | Column 4 |
| --- | --- | --- | --- | --- |
| 1 | Dirt | Stone | Iron ore | Coal ore |
| 2 | Lead ore | Crystal ore | Sand | Wood |

`terrain_tiles.png` is the packaged 64×32 runtime atlas, with one 16×16 swatch
per material. Rebuild it with `uv run python tools/prepare_terrain.py`.
The compiler crops proportional cell boundaries, samples nearest neighbors,
then maps to the 13-color palette in `ttx.world.materials`. Both master and
runtime PNGs ship in the wheel; there is no external file dependency.

A world tile occupies 8×8 logical dots (4 columns × 2 terminal rows). Textures
repeat across 2×2 world tiles and remain anchored in world space during camera
movement. Opaque Unicode quadrant blocks replace the old dotted masks and
black tile seams. Each terminal cell chooses two palette colors for four
quadrants; there is no dim attribute, blur, interpolated color or shadow pass.
The quadrant display resolves eighth-tile horizontal and quarter-tile vertical
steps. On 256-color terminals the palette uses standard xterm colors, with
an eight-color fallback for basic terminals. Grass adds a crisp green top edge.

Player poses are code-authored on the existing 8×8 sprite grid, including an
eight-phase distance-driven walk cycle, facing, rising, falling and landing.
They do not change collision boxes or authoritative physics. Camera changes
switch directly to the next page on both axes, with overlap/hysteresis to
prevent repeated switches near an edge. Terrain is rebuilt once per page
change and cached between changes. There is no scrolling animation or delay;
fast falls, layout changes and teleports keep the player visible immediately.

Preview the actual terminal cell composition with:

```bash
uv run python tools/preview_world.py
uv run python tools/preview_motion.py
```

The tools write a world PNG, actor/camera GIFs and CPU frame-composition timings
to `dist/`. These previews emulate the game's cells, rather than a specific
terminal font; timings exclude terminal output and are not an FPS guarantee.

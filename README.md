
# Kard-X Sandbox


A terminal sandbox RPG with multiplayer exploration and Kard-X card battles. Install the `kard-x-sandbox` package and launch it with `ttx`.

 


Kard-X Sandbox combines TTG-style multiplayer sandbox exploration with Kard-X's data-driven card battle system. The original `kardx` Python package provides the card engine and legacy game modes; the `ttx` package provides the multiplayer world.

## Features

-   **Multiplayer Sandbox:** Host or join a shared side-view world with gravity, jumping, mining, building, enemies, and resources.
-   **Layered Terrain:** Explore seeded hills, grass and sand surfaces, soil, rock, underground tunnels, caves, and clustered mineral deposits.
-   **Smooth Controls:** Local prediction responds before a server reply, with 60 Hz motion frames, quick braking, air steering, and forgiving jump timing.
-   **Roaming Enemies:** Enemies patrol, pause and turn, spot players through clear lines of sight, briefly search their last seen position, and jump over small obstacles. The server updates the world even when players are idle.
-   **Stable Terminal Rendering:** Opaque Unicode pixel blocks replace dotted terrain and dim shadows. Fixed camera pages reuse cached terrain; only changed terminal cells are sent to the screen.
-   **Pixel Art and Scene Changes:** Eight packaged PNG materials cover dirt, stone, iron, coal, lead, crystal, sand and wood. Players have distance-driven steps, facing and airborne/landing poses. All four map edges switch directly to the next viewport in one frame, while battle entry retains its diagonal sparkling wipe.
-   **Real Pause:** Pausing freezes the player, including an airborne jump. The whole world freezes when all connected players are paused.
-   **Data-Driven Design:** All cards and characters are defined in simple `.jsonc` files. Modifying the game or creating new content is as easy as editing a text file!
-   **Strategic Depth:** Manage your Health (HP), Defense (DEF), and Mana to outwit your opponent. Grow stronger by permanently increasing your Max Mana.
-   **Card Battles:** World enemies launch Kard-X card battles instead of the old TTG guessing minigame.
-   **Adventure Mode:** Choose routes through a multi-node run with battles, events, shops, rest sites, elites, and a final boss.
-   **Sandbox Mode:** Explore a continuous room-based world, gather materials, craft items or cards, and enter Kard-X card battles when enemies block the path.
-   **Run Progression:** Carry HP, Gold, deck changes, relics, defeated enemies, and event outcomes across an adventure.
-   **Rarity-Aware Rewards:** Card rewards favor common tools, with rare scaling cards like `Mana Crystal` appearing less often.
-   **Infinite Replayability:** Choose from different hero archetypes, shape your deck, and face unique enemies.

## Installation

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) 0.12.7 or newer. Play the latest published version without cloning this repository:

```bash
uvx --from kard-x-sandbox ttx
```

For a persistent installation:

```bash
uv tool install kard-x-sandbox
ttx
```

Check the installed version with `ttx --version`; `ttx --help` shows command information without opening the game. The game needs an interactive terminal. Windows Terminal is recommended on Windows; Linux terminals need a working curses/terminfo installation. Python 3.10 and newer are supported.

For development, clone the repository and run:

```bash
uv sync
```

Start the multiplayer sandbox:

```bash
uv run ttx
```

Legacy Kard-X entry points are still available while the projects are being merged:

```bash
uv run kardx
uv run sandkard
```

`uv run` also installs the project and its dependencies automatically, so you can start with just `uv run ttx`. No virtual environment activation is needed. The project supports Python 3.10 or higher; uv uses Python 3.12 by default and downloads it if needed.

The public package name is `kard-x-sandbox`, the main command is `ttx`, and the Python modules remain `ttx` and `kardx`.

If this checkout was previously installed as the `ttx` distribution, rebuild its shared command launchers once after the rename:

```bash
uv sync --locked --reinstall-package kard-x-sandbox
uv run --locked ttx --version
```

## Development

`uv sync` installs the project in editable mode along with the development dependencies. Run the existing tests with:

```bash
uv run pytest
```

See the [changelog](https://github.com/JohnnyWu2k/kardx/blob/main/CHANGELOG.md) for release notes and the [release guide](https://github.com/JohnnyWu2k/kardx/blob/main/RELEASING.md) for distribution checks and publication steps.

Public documentation, including this README, the changelog, and the release guide, is written in English. Personal reviews, development notes, and Traditional Chinese versions belong in the local `docs/` directory. That directory is ignored by Git and excluded from distribution archives.

Manage dependencies and their lockfile with uv:

```bash
uv add PACKAGE
uv add --dev PACKAGE
uv remove PACKAGE
uv lock --upgrade
```

Commit `pyproject.toml`, `uv.lock`, and `.python-version` together. Use `uv sync --locked` and `uv run --locked pytest` when you want to require the committed dependency versions. GitHub Actions runs the tests on Linux and Windows with Python 3.10 and 3.12, and builds both distribution formats.

## Build and publish

Build the source distribution and wheel into a dedicated release directory:

```bash
uv build --no-sources --out-dir dist/release
uv run --locked python tools/check_release.py dist/release --write-checksums
```

Before a subsequent release, update the version with `uv version --bump patch` (or `minor` / `major`), update the changelog, run the tests, and rebuild. Runtime version information comes from the installed package metadata. The maintainer performs the upload manually, using the exact two files for the intended release:

```bash
uv publish --trusted-publishing never dist/release/kard_x_sandbox-0.2.0.tar.gz dist/release/kard_x_sandbox-0.2.0-py3-none-any.whl
```

Supply your PyPI API token through the `UV_PUBLISH_TOKEN` environment variable. Use explicit filenames because `dist/` may also contain older TTX builds. Add `--dry-run` to the command above to check the upload plan without publishing.

For a trial upload, set `UV_PUBLISH_TOKEN` to a **TestPyPI** token and run:

```bash
uv publish --index testpypi --trusted-publishing never dist/release/kard_x_sandbox-0.2.0.tar.gz dist/release/kard_x_sandbox-0.2.0-py3-none-any.whl
```

The manual **Prepare release** GitHub Actions workflow validates the distributions and provides downloadable release artifacts. It does not upload to PyPI. See [RELEASING.md](https://github.com/JohnnyWu2k/kardx/blob/main/RELEASING.md) for the full verification and manual upload procedure.

## How to Play

The `ttx` command opens a centered host/join menu. Click an option with the left mouse button, or use Up/Down (or `W`/`S`) and Enter. Settings uses the same controls, including after a window resize.

Mouse controls work throughout the `ttx` flow, including Connect/Back, the world, inventory, and both pause menus. The reticle follows the pointer immediately. With a block selected, left-click places it within two tiles; with a tool or empty hand, left-click gathers/mines an adjacent tile or enters combat with an adjacent enemy. The selected tool, its ownership and harvesting tier are checked by the server. Right-click anywhere hides the reticle; left-click or selecting a hotbar slot restores it. There is no Build-mode toggle. Distances use Manhattan tiles; the reticle turns red outside the selected action's reach.

Hold the left button to repeat mining or placement every 120 ms at the current pointer target, including while dragging. Release, right-click, changing slots, leaving the world area, or opening a menu stops the action. Depleting a block stack stops placement instead of switching to mining; repeated mining does not automatically start combat. Windows also detects a release outside the terminal and stops held actions when the terminal loses focus.

The right panel has ten hotbar slots. Select with `1`–`9`, `0` (slot 10), the wheel or a click. Empty slots show only their number; items and counts appear when owned, and there is no duplicate item summary. Press `E` for a centered 25-slot backpack over the frozen world. Hover or use arrow keys to select a slot; click/Enter equips it (items in slots 11–25 swap into the active hotbar slot). Press `1`–`9` or `0` while hovering to swap into that hotbar position. Press `E` or `Esc` to close. Slot order persists in the world save. The backpack pauses movement and gravity using the same rules as Pause.

In battle, click a card to select it, then click Play or Discard; End turn and Pause are also clickable. The wheel and arrow keys change the selected card. Opponents stand behind their cards in the centered arena, and player cards use the packaged fantasy pixel-art atlas, with two independently colored pixels per terminal cell. Hands are horizontally centered in the lower half of the screen; larger terminals show taller illustrations. Short terminals use a compact layout; 80×24 or larger shows the illustrations. Frames finish their buffered update even while mouse-motion events arrive, with terminal scrolling disabled during drawing.

Settings includes Particle color (seven palettes), Transition duration (0 to 3 seconds), and Preview transition. Duration is the combined cover/reveal animation time, excluding data-loading waits. Set duration to 0 to disable the effect. Values persist with the existing Kard-X settings. Dirt and stone now use fixed, world-anchored PNG texture samples; all terrain still uses an 8x8-dot world tile with visible tile seams. Asset provenance and the generation prompt are in `src/ttx/assets/README.md`.

Harvesting progression is enforced on the server:

| Material | Minimum tool |
| --- | --- |
| Wood, dirt, sand, workbench | Hand |
| Stone, coal | Wood pickaxe |
| Iron ore, lead ore | Stone pickaxe |
| Crystal | Iron pickaxe |

Craft sticks from 2 wood (4 sticks), and a workbench from 4 wood. Select the bench in the hotbar and left-click to place it, then stand within two tiles and press `C`. A wood pickaxe costs 3 wood + 2 sticks; stone costs 3 stone + 2 sticks; iron costs 3 iron ore + 2 sticks. This first crafting version uses raw iron ore directly; smelting and torch recipes are not yet implemented.

Combat has separate player/enemy panels on wide terminals, prominent HP/Mana bars, and highlighted numeric deltas for health, mana and defense. Logs and deck counts sit below the arena. Narrow terminals use a compact layout.

Windows movement uses physical key polling rather than committed IME text when the owning console/Windows Terminal window can be resolved. Named-world and IP fields use Unicode `get_wch` input and handle wide characters. IME candidates and composition remain managed by the terminal; actual behavior depends on the host terminal. Arrow keys remain an alternative on hosts without native key polling.

For a reproducible layout preview, run `uv run python tools/preview_interface.py` (optional `--columns` and `--rows`); it writes `dist/battle-preview.png`.

- Host a game: create a named world (Unicode names supported), or load a saved world. World terrain, collected objects, enemies, player inventories and card progression persist. Saves use atomic replacement, run every 30 seconds and on shutdown, and are also available from Pause > Save world. On Windows they live in `%APPDATA%/Kard-X/worlds`; keep the adjacent `player-id.txt` to retain your player identity.
- Join by entering the host IP address, or click Search LAN below Connect. Discovery uses UDP 12346; gameplay uses TCP 12345. A LAN that blocks broadcast can still use manual IP entry.
- Open Settings, then Fullscreen, to maximize the terminal window.
- Hold `A` / `D` or the left/right arrow keys to walk, with a short acceleration and braking curve. Left/right steering also works while jumping or falling.
- Jump with `W`, Up, or Space. Gravity brings players and enemies back to the ground. A jump pressed up to 150 ms before landing is buffered, and a 100 ms grace period lets you jump just after leaving an edge.
- Toggle the default smooth dot graphics and the original text display with `V`.
- Left-click a target to gather or enter Kard-X combat. G/X/S mining shortcuts have been removed; movement and text input are separate.
- Select a block to place it, or a tool/empty slot to gather. Click Crafting (or C) to make sticks/workbenches by hand and tools near a placed workbench. Mining uses the selected pickaxe; empty hands still obey the material's minimum tool tier.

Press `Esc` for a pause overlay; `Esc` or Resume returns to exploration, and Quit returns to the host/join menu. Pause freezes your position and gravity without discarding fractional movement. In a single-player session, the world, enemies, and simulation timers also freeze. In multiplayer, other active players can continue; the whole world freezes when everyone is paused. The pause menu inside card combat follows the same rule. Movement input is released when opening a menu/backpack or entering combat.

Windows supports independent held movement and jump keys, including release detection, brief taps, and stopping input when the terminal loses focus. Holding jump does not repeatedly jump on Windows. Terminals that supply only repeated key presses use a short movement timeout; their initial hold response depends on the terminal's repeat delay. Local movement is predicted immediately and unacknowledged inputs are replayed after each server snapshot, so ordinary network latency does not pull the player back to an older position. Input frames run at 60 Hz while the server sends world snapshots at 20 Hz; other actors interpolate between snapshots. The server limits simulation speed and expires stale movement input after 350 ms.

The terminal shows a Terraria-inspired side view with a camera that follows the player horizontally and vertically. The camera stays fixed while the player moves inside the viewport. At a one-tile edge margin it switches directly to the next viewport with a small overlap. Each switch takes one frame with no intermediate scrolling, fade or delay; subsequent frames reuse the terrain cache. The overlap gives enough room to reverse direction without repeatedly flipping screens. Both axes support this behavior; resizing and teleporting keep the player visible. Dot graphics give each world tile an 8 by 8 dot area across four terminal columns and two rows. The player and terrain share that projection, reducing movement increments to one eighth of a tile. Terminal graphics still have a finite grid; use `V` for the original text view if the terminal font does not display the dot characters well. The default world spans 512 by 192 tiles and loads terrain in chunks. The server shares the world dimensions and seed so clients with different terminal sizes see the same terrain. The right-side status panel keeps roughly one quarter of the terminal width across the supported window presets.

Enemies normally roam around their spawn area. Within 12 tiles (Manhattan distance), they acquire the closest available player with an unobstructed view. Terrain and placed blocks block sight, including solid diagonal corners. They keep a visible target within 16 tiles; when sight is lost, they search the last seen position for about 800 ms before returning to patrol. They stop next to the player for left-click card combat; there is no automatic contact damage. During a card battle, the participating player and enemy stay fixed while the rest of the shared world continues running. The scene sweeps from the upper left to the lower right, flashes symbols while battle data is prepared, and sweeps back to reveal the completed frame. Returning to the world uses the same transition without clearing terminal history.

Victory reward cards join your deck for later battles. Defeat returns you to exploration with at least 1 HP, following the legacy sandbox's nonlethal retreat rule.

The default dot view draws [compressed tree and grass-path PNGs](https://github.com/JohnnyWu2k/kardx/tree/main/src/ttx/assets) through the terminal canvas. The source prompts requested a single transparent, six-color woodland tree with a clear silhouette, and a horizontally repeating pixel-art grass-and-earth path with stones. [`tools/prepare_pixel_art.py`](https://github.com/JohnnyWu2k/kardx/blob/main/tools/prepare_pixel_art.py) crops and quantizes the generated source images into the small runtime assets. Terminals with native image protocols can show higher-resolution graphics: [Kitty's graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/) and [Windows Terminal's SIXEL support](https://github.com/microsoft/terminal/discussions/17809) are examples. The current in-game renderer uses Unicode dots for portability; a native image-protocol backend can be added later without changing the source PNGs or the battle loading transition.

Terrain uses layered, smoothly interpolated value noise for elevation, biomes, caves, and mineral veins, plus winding underground tunnels. This follows common [noise-based terrain generation principles](https://www.redblobgames.com/maps/terrain-from-noise/); it is an original implementation inspired by Minecraft and Terraria rather than a copy of either game's generator.

Editable card and character data is copied from the packaged defaults into your user data directory the first time you open a data file from the in-game editor. Restart the game after saving those files.

## Game Concept

The legacy `kardx` command offers Sandbox Mode for room-based exploration, Adventure Mode for a full route-based run, and Quick Battle for the classic single fight. The primary `ttx` command opens the multiplayer host/join menu described above. Each character begins with a unique starting deck.

-   **Objective:** Reduce the enemy's HP to zero.
-   **Turns:** Each turn, you draw 5 cards and your Mana is refilled. Play cards by spending Mana.
-   **Card Effects:**
    -   **Attack:** Deal damage to the enemy.
    -   **Defense:** Gain DEF to block incoming damage for one turn.
    -   **Power:** Play cards like `Mana Crystal` to permanently increase your Max Mana, enabling more powerful combos in later turns.
-   **Deck Cycling:** Played cards go to discard. When the draw deck runs out, the discard pile is shuffled back into the deck.
-   **Adventure Nodes:** Routes are generated from editable node pools with controlled pacing. Early routes build your deck, shops and rest sites appear before major difficulty jumps, elites can grant relics, and events can upgrade cards or reshape resources.
-   **Sandbox Exploration:** Move with commands like `go north`, collect items with `take`, gather materials with `forage`, and turn materials into cards or useful items with `craft`.

## Editable Content

The Content Editor can open the game's editable JSONC files:

-   `cards.jsonc` for card definitions.
-   `characters.jsonc` for playable characters and enemies.
-   `adventures.jsonc` for route maps and reward pools.
-   `events.jsonc` for non-combat choices.
-   `relics.jsonc` for passive run modifiers.
-   `world.jsonc` for Sandbox Mode rooms, exits, ground items, foraging pools, and talk hooks.
-   `recipes.jsonc` for material-based crafting that can add items, add cards, or upgrade cards.
-   `encounters.jsonc` for room-triggered Sandbox Mode battles and victory rewards.

## Current limits

Multiplayer currently targets trusted local or LAN sessions on TCP port 12345. Card battle results are reported by the client; server-side turn verification is planned. Named multiplayer worlds have separate versioned saves. Legacy room-based Sandbox Mode retains its own save slots. Coal is collected for future torch recipes; lead is collectible, with more uses planned.

Windows is tested locally, and CI covers Linux and Windows on Python 3.10 and 3.12. Linux terminal interaction still needs a manual playthrough before claiming the same level of gameplay validation.

## Roadmap (Future Development)

Kard-X Sandbox is built to be expanded. Here's what's planned for the future:

-   [x] **Card Reward System:** Gain new cards after winning a battle.
-   [x] **More Enemies & Bosses:** Introduce enemies with unique AI and abilities.
-   [x] **Relics & Artifacts:** Add passive items that grant special bonuses.
-   [x] **Event System:** Encounter non-combat events that offer choices and consequences.
-   [x] **Multiplayer World:** Host or join a shared sandbox map.
-   [ ] **Server-Verified Card Battles:** Move beyond local battle result reporting.


## License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/JohnnyWu2k/kardx/blob/main/LICENSE) file for details.


*Built with passion and Python.*

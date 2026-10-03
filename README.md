
# Kard-X Sandbox


A terminal sandbox RPG with multiplayer exploration and Kard-X card battles. Install the `kard-x-sandbox` package and launch it with `ttx`.

 


Kard-X Sandbox combines TTG-style multiplayer sandbox exploration with Kard-X's data-driven card battle system. The original `kardx` Python package provides the card engine and legacy game modes; the `ttx` package provides the multiplayer world.

## Features

-   **Multiplayer Sandbox:** Host or join a shared side-view world with gravity, jumping, mining, building, enemies, and resources.
-   **Layered Terrain:** Explore seeded hills, grass and sand surfaces, soil, rock, underground tunnels, caves, and clustered mineral deposits.
-   **Smooth Controls:** Local prediction responds before a server reply, with 60 Hz motion frames, quick braking, air steering, and forgiving jump timing.
-   **Roaming Enemies:** Enemies patrol, pause and turn, spot players through clear lines of sight, briefly search their last seen position, and jump over small obstacles. The server updates the world even when players are idle.
-   **Stable Terminal Rendering:** Unicode dot graphics move in quarter-tile increments at up to 60 frames per second. Only changed cells are sent to the terminal; menus and card battles share the same screen.
-   **Pixel Art and Scene Changes:** Compressed PNG sprites provide trees and a textured grass path. Battle entry uses a diagonal, sparkling wipe while card data loads, then reveals the ready scene in reverse.
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

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) 0.12.7 or newer. Once version 0.1.0 is published to PyPI, play without cloning this repository:

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
uv publish dist/release/kard_x_sandbox-0.1.0.tar.gz dist/release/kard_x_sandbox-0.1.0-py3-none-any.whl
```

Supply your PyPI API token through the `UV_PUBLISH_TOKEN` environment variable. Use explicit filenames because `dist/` may also contain older TTX builds. Add `--dry-run` to the command above to check the upload plan without publishing.

For a trial upload, set `UV_PUBLISH_TOKEN` to a **TestPyPI** token and run:

```bash
uv publish --index testpypi dist/release/kard_x_sandbox-0.1.0.tar.gz dist/release/kard_x_sandbox-0.1.0-py3-none-any.whl
```

The manual **Prepare release** GitHub Actions workflow validates the distributions and provides downloadable release artifacts. It does not upload to PyPI. See [RELEASING.md](https://github.com/JohnnyWu2k/kardx/blob/main/RELEASING.md) for the full verification and manual upload procedure.

## How to Play

The `ttx` command opens a centered host/join menu. Click an option with the left mouse button, or use Up/Down (or `W`/`S`) and Enter. Settings uses the same controls, including after a window resize.

- Host a game to start a local server and connect to it.
- Join a game by entering the host IP address.
- Open Settings, then Fullscreen, to maximize the terminal window.
- Hold `A` / `D` or the left/right arrow keys to walk, with a short acceleration and braking curve. Left/right steering also works while jumping or falling.
- Jump with `W`, Up, or Space. Gravity brings players and enemies back to the ground. A jump pressed up to 150 ms before landing is buffered, and a 100 ms grace period lets you jump just after leaving an edge.
- Toggle the default smooth dot graphics and the original text display with `V`.
- Gather trees or mine the tile you are facing with `G`.
- Mine directly below your feet with `S` or Down to enter the underground layers.
- Trigger Kard-X card combat against adjacent enemies with `X`.
- Toggle build mode with `B`; use `WASD` or arrows to aim at an adjacent tile, `1` / `2` / `3` / `4` to select wood / stone / dirt / sand, then Enter to place a block. Placing a block consumes one material. `G` mines in the selected direction while build mode is active.

Press `Esc` for a pause overlay; `Esc` or Resume returns to exploration, and Quit returns to the host/join menu. Pause freezes your position and gravity without discarding fractional movement. In a single-player session, the world, enemies, and simulation timers also freeze. In multiplayer, other active players can continue; the whole world freezes when everyone is paused. The pause menu inside card combat follows the same rule. Movement input is released when opening a menu or entering build mode or combat.

Windows supports independent held movement and jump keys, including release detection, brief taps, and stopping input when the terminal loses focus. Holding jump does not repeatedly jump on Windows. Terminals that supply only repeated key presses use a short movement timeout; their initial hold response depends on the terminal's repeat delay. Local movement is predicted immediately and unacknowledged inputs are replayed after each server snapshot, so ordinary network latency does not pull the player back to an older position. Input frames run at 60 Hz while the server sends world snapshots at 20 Hz; other actors interpolate between snapshots. The server limits simulation speed and expires stale movement input after 350 ms.

The terminal shows a Terraria-inspired side view with a camera that follows the player horizontally and vertically. A camera dead zone keeps small steps and short jumps from scrolling the whole map; a gradual entry into scrolling avoids a sudden camera start. Camera movement depends on player displacement and stops when the player stops, without continuing to drift. Dot graphics give each world tile a 4 by 4 dot area across two terminal columns and one row. The player and terrain share that projection, reducing movement increments to one quarter of a tile. Terminal graphics still have a finite grid; use `V` for the original text view if the terminal font does not display the dot characters well. The default world spans 512 by 192 tiles and loads terrain in chunks. The server shares the world dimensions and seed so clients with different terminal sizes see the same terrain. The right-side status panel keeps roughly one quarter of the terminal width across the supported window presets.

Enemies normally roam around their spawn area. Within 12 tiles (Manhattan distance), they acquire the closest available player with an unobstructed view. Terrain and placed blocks block sight, including solid diagonal corners. They keep a visible target within 16 tiles; when sight is lost, they search the last seen position for about 800 ms before returning to patrol. They stop next to the player for `X` card combat; there is no automatic contact damage. During a card battle, the participating player and enemy stay fixed while the rest of the shared world continues running. The scene sweeps from the upper left to the lower right, flashes symbols while battle data is prepared, and sweeps back to reveal the completed frame. Returning to the world uses the same transition without clearing terminal history.

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

Multiplayer currently targets trusted local or LAN sessions on TCP port 12345. Card battle results are reported by the client; server-side turn verification is planned. A multiplayer world lasts for the running host session and does not yet have save/load support. Save slots belong to the legacy room-based Sandbox Mode.

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

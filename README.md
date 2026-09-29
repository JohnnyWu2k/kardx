
# TTX


A multiplayer sandbox RPG that uses Kard-X style card battles.

 


TTX combines TTG-style multiplayer sandbox exploration with Kard-X's data-driven card battle system. The original Kard-X package is kept inside this repository as the card engine while new multiplayer sandbox systems live under the `ttx` package.

## Features

-   **Multiplayer Sandbox:** Host or join a shared side-view world with gravity, jumping, mining, building, enemies, and resources.
-   **Layered Terrain:** Explore seeded hills, grass and sand surfaces, soil, rock, underground tunnels, caves, and clustered mineral deposits.
-   **Smooth Controls:** Local prediction responds before a server reply, with 60 Hz motion frames, quick braking, air steering, and forgiving jump timing.
-   **Roaming Enemies:** Enemies patrol, pause and turn, spot players through clear lines of sight, briefly search their last seen position, and jump over small obstacles. The server updates the world even when players are idle.
-   **Stable Terminal Rendering:** Unicode dot graphics move in quarter-tile increments at up to 60 frames per second. Only changed cells are sent to the terminal; menus and card battles share the same screen.
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

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) 0.12.7 or newer, then run these commands from the repository:

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

Once this TTX package is published to PyPI, users can play without cloning the repository:

```bash
uvx ttx
```

For a persistent installation, use `uv tool install ttx`, then launch with `ttx`.

## Development

`uv sync` installs the project in editable mode along with the development dependencies. Run the existing tests with:

```bash
uv run pytest
```

Manage dependencies and their lockfile with uv:

```bash
uv add PACKAGE
uv add --dev PACKAGE
uv remove PACKAGE
uv lock --upgrade
```

Commit `pyproject.toml`, `uv.lock`, and `.python-version` together. Use `uv sync --locked` and `uv run --locked pytest` when you want to require the committed dependency versions. GitHub Actions runs the tests on Linux and Windows with Python 3.10 and 3.12, and builds both distribution formats.

## Build and publish

Build the source distribution and wheel into `dist/`:

```bash
uv build
```

Before a subsequent release, update the version with `uv version --bump patch` (or `minor` / `major`), run the tests, and rebuild. To avoid uploading old releases from `dist/`, publish only the files for the intended version; for the current version:

```bash
uv publish dist/ttx-0.1.0.tar.gz dist/ttx-0.1.0-py3-none-any.whl
```

Supply your PyPI API token through the `UV_PUBLISH_TOKEN` environment variable. If `dist/` contains only the intended release, the upload command is simply `uv publish`. You can check the files without uploading with `uv publish --dry-run`.

For a trial upload, set `UV_PUBLISH_TOKEN` to a **TestPyPI** token and run:

```bash
uv publish --index testpypi dist/ttx-0.1.0.tar.gz dist/ttx-0.1.0-py3-none-any.whl
```

The manual **Publish to PyPI** GitHub Actions workflow also uses uv for dependency installation, tests, building, and publishing. To enable it, create a GitHub environment named `pypi` and configure a [PyPI Trusted Publisher](https://docs.pypi.org/trusted-publishers/) for this repository, workflow `publish.yml`, and environment `pypi`. Commit the release version and lockfile, then run the workflow on that commit from the Actions tab. It uses Trusted Publishing instead of a stored API token.

## How to Play

The `ttx` command opens a host/join menu.

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

Enemies normally roam around their spawn area. Within 12 tiles (Manhattan distance), they acquire the closest available player with an unobstructed view. Terrain and placed blocks block sight, including solid diagonal corners. They keep a visible target within 16 tiles; when sight is lost, they search the last seen position for about 800 ms before returning to patrol. They stop next to the player for `X` card combat; there is no automatic contact damage. During a card battle, the participating player and enemy stay fixed while the rest of the shared world continues running. Combat opens and closes with a short scene reveal, without leaving the curses screen or clearing the terminal history.

Terrain uses layered, smoothly interpolated value noise for elevation, biomes, caves, and mineral veins, plus winding underground tunnels. This follows common [noise-based terrain generation principles](https://www.redblobgames.com/maps/terrain-from-noise/); it is an original implementation inspired by Minecraft and Terraria rather than a copy of either game's generator.

Editable card and character data is copied from the packaged defaults into your user data directory the first time you open a data file from the in-game editor. Restart the game after saving those files.

## Game Concept

The main menu offers Sandbox Mode for free-form exploration, Adventure Mode for a full route-based run, and Quick Battle for the classic single fight. Each character begins with a unique starting deck.

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

## Roadmap (Future Development)

TTX is built to be expanded. Here's what's planned for the future:

-   [x] **Card Reward System:** Gain new cards after winning a battle.
-   [x] **More Enemies & Bosses:** Introduce enemies with unique AI and abilities.
-   [x] **Relics & Artifacts:** Add passive items that grant special bonuses.
-   [x] **Event System:** Encounter non-combat events that offer choices and consequences.
-   [x] **Multiplayer World:** Host or join a shared sandbox map.
-   [ ] **Server-Verified Card Battles:** Move beyond local battle result reporting.


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


*Built with passion and Python.*

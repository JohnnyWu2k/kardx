
# Kard-X


A minimalist, data-driven, text-based card battler that runs directly in your terminal.

 


Welcome to Kard-X, a pure command-line interface (CLI) card game where strategy meets simplicity. Built with Python and designed for extensibility, Kard-X offers a classic deck-builder experience with a modern, tech-inspired feel.

## Features

-   **Purely Text-Based:** Enjoy a clean, distraction-free, and retro-cool gaming experience in your terminal.
-   **Data-Driven Design:** All cards and characters are defined in simple `.jsonc` files. Modifying the game or creating new content is as easy as editing a text file!
-   **Strategic Depth:** Manage your Health (HP), Defense (DEF), and Mana to outwit your opponent. Grow stronger by permanently increasing your Max Mana.
-   **Adventure Mode:** Choose routes through a multi-node run with battles, events, shops, rest sites, elites, and a final boss.
-   **Run Progression:** Carry HP, Gold, deck changes, relics, defeated enemies, and event outcomes across an adventure.
-   **Rarity-Aware Rewards:** Card rewards favor common tools, with rare scaling cards like `Mana Crystal` appearing less often.
-   **Infinite Replayability:** Choose from different hero archetypes, shape your deck, and face unique enemies.

## Installation

You can install Kard-X directly from PyPI with a single command:

```bash
pip install kard-x
```

For local development, install it from the repository in editable mode:

```bash
python -m pip install -e .
```

*Requires Python 3.10 or higher.*

## How to Play

After installation, start the game with the console command:

```bash
kardx
```

You can also launch the installed package as a module:

```bash
python -m kardx
```

The old repository-only command still works as a compatibility shim:

```bash
python -m src.main
```

Editable card and character data is copied from the packaged defaults into your user data directory the first time you open a data file from the in-game editor. Restart the game after saving those files.

## Game Concept

The main menu offers Adventure Mode for a full route-based run and Quick Battle for the classic single fight. Each character begins with a unique starting deck.

-   **Objective:** Reduce the enemy's HP to zero.
-   **Turns:** Each turn, you draw 5 cards and your Mana is refilled. Play cards by spending Mana.
-   **Card Effects:**
    -   **Attack:** Deal damage to the enemy.
    -   **Defense:** Gain DEF to block incoming damage for one turn.
    -   **Power:** Play cards like `Mana Crystal` to permanently increase your Max Mana, enabling more powerful combos in later turns.
-   **Deck Cycling:** Played cards go to discard. When the draw deck runs out, the discard pile is shuffled back into the deck.
-   **Adventure Nodes:** Routes are generated from editable node pools with controlled pacing. Early routes build your deck, shops and rest sites appear before major difficulty jumps, elites can grant relics, and events can upgrade cards or reshape resources.

## Editable Content

The Content Editor can open the game's editable JSONC files:

-   `cards.jsonc` for card definitions.
-   `characters.jsonc` for playable characters and enemies.
-   `adventures.jsonc` for route maps and reward pools.
-   `events.jsonc` for non-combat choices.
-   `relics.jsonc` for passive run modifiers.

## Roadmap (Future Development)

Kard-X is built to be expanded. Here's what's planned for the future:

-   [x] **Card Reward System:** Gain new cards after winning a battle.
-   [x] **More Enemies & Bosses:** Introduce enemies with unique AI and abilities.
-   [x] **Relics & Artifacts:** Add passive items that grant special bonuses.
-   [x] **Event System:** Encounter non-combat events that offer choices and consequences.
-   [ ] **Color Support:** Using libraries like `colorama` or `rich` to enhance the UI.


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


*Built with passion and Python.*

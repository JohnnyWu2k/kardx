
# Kard-X


A minimalist, data-driven, text-based card battler that runs directly in your terminal.

 


Welcome to Kard-X, a pure command-line interface (CLI) card game where strategy meets simplicity. Built with Python and designed for extensibility, Kard-X offers a classic deck-builder experience with a modern, tech-inspired feel.

## Features

-   **Purely Text-Based:** Enjoy a clean, distraction-free, and retro-cool gaming experience in your terminal.
-   **Data-Driven Design:** All cards and characters are defined in simple `.jsonc` files. Modifying the game or creating new content is as easy as editing a text file!
-   **Strategic Depth:** Manage your Health (HP), Defense (DEF), and Mana to outwit your opponent. Grow stronger by permanently increasing your Max Mana.
-   **Infinite Replayability:** A robust card-cycling system ensures the battle never ends. Choose from different hero archetypes and face unique enemies.

## Installation

You can install Kard-X directly from PyPI with a single command:

```bash
pip install kard-x
```

or you can download and build it from this command:
```bash
python main.py
```

*Requires Python 3.10 or higher.*

## How to Play

After installation, simply type the following command in your terminal to start the game:

```bash
kardx
```

## Game Concept

The game starts with a Character Selection screen. Each character begins with a unique starting deck.

-   **Objective:** Reduce the enemy's HP to zero.
-   **Turns:** Each turn, you draw 5 cards and your Mana is refilled. Play cards by spending Mana.
-   **Card Effects:**
    -   **Attack:** Deal damage to the enemy.
    -   **Defense:** Gain DEF to block incoming damage for one turn.
    -   **Power:** Play cards like `Mana Crystal` to permanently increase your Max Mana, enabling more powerful combos in later turns.
-   **Deck Cycling:** When your draw pile is empty, your discard pile is automatically shuffled back into it, allowing you to use your cards indefinitely.

## Roadmap (Future Development)

Kard-X is built to be expanded. Here's what's planned for the future:

-   [ ] **Card Reward System:** Gain new cards after winning a battle.
-   [ ] **More Enemies & Bosses:** Introduce enemies with unique AI and abilities.
-   [ ] **Relics & Artifacts:** Add passive items that grant special bonuses.
-   [ ] **Event System:** Encounter non-combat events that offer choices and consequences.
-   [ ] **Color Support:** Using libraries like `colorama` or `rich` to enhance the UI.


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


*Built with passion and Python.*

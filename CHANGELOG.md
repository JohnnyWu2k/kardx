# Changelog

## 0.2.0 — persistent worlds, inventory and terminal graphics

- Create and load named worlds, including Unicode names. Save terrain changes, world objects, enemies, player inventories, hotbar order and card progression with atomic writes, periodic autosaves and a Save option in Pause.
- Discover hosted worlds on the local network or connect by entering the host address.
- Add crafting, workbenches and pickaxe progression, with material ownership, selected tools, harvesting tiers and placement reach validated by the server.
- Replace the fixed five-item inventory and duplicate material summary with a ten-slot hotbar and a centered 25-slot backpack opened with `E`. Empty slots show only their numbers; hover, click, arrow keys and slot shortcuts support selection and arrangement.
- Make the selected item determine the left-button action: blocks place, tools and empty hands gather. Hold the button to repeat every 120 ms at the current pointer target; release, slot changes and menus cancel the action. Right-click hides the reticle, and depleted block stacks never switch to digging during a hold.
- Package eight terrain textures and fantasy card artwork. Draw opaque terrain without dotted shadows or dark tile seams, and add directional walking, jumping, falling and landing poses.
- Switch directly to the next viewport at all four edges, with overlap to prevent repeated page changes. Reuse cached terrain between switches and update only changed terminal cells.
- Improve mouse support across world, crafting, inventory, menus and card battles; add configurable battle transition duration and particle colors.
- Fix Unicode world-name input and wide-character redraws that left text in loading screens or the world. Improve Windows Terminal input ownership, free mouse movement reports and held-button release detection.

Multiplayer battle results and player identity remain client-reported; this release targets trusted local/LAN play. Worlds are saved on the host. A manual Linux terminal playthrough remains outstanding.

## 0.1.0 — first public release

Published package: `kard-x-sandbox`. Main command: `ttx`.

- Host or join a shared side-view sandbox with seeded terrain, mining, building, roaming enemies, and Kard-X card battles.
- Predict local movement, interpolate other actors, and render Unicode dot graphics with packaged pixel art and battle transitions.
- Keep the legacy `kardx` adventure/quick-battle menu and `sandkard` room-based sandbox available.
- Make server startup, shutdown, rehosting, snapshot delivery, and JSON framing reliable; reject malformed commands and snapshots.
- Correct lethal battle effects, resource bounds, event/crafting transactions, reward synchronization, and retreat handling.
- Protect settings and legacy sandbox saves with validation and atomic writes.
- Correct wide-character rendering, narrow-window card selection, screen cache invalidation, and Unix keyboard handling.
- Provide `ttx --help` and `ttx --version`, with the version read from installed package metadata.
- Bind Windows native input and window maximization to the game's console owner instead of whichever application has foreground focus.
- Validate the installed distribution, bundled game data and sprites, and source archive before manual publication.

Multiplayer battle results are still client-reported, and multiplayer worlds are session-only. This release is intended for trusted local/LAN play. Linux has automated coverage; a manual Linux terminal playthrough remains outstanding.

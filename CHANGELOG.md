# Changelog

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

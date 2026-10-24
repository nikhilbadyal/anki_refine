# Changelog

All notable changes to Refine are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/) (0.x = beta).

## [0.2.1] - 2026-10-24

### Changed
- Clicking a deck name on Home now selects it and stays on Home (the headline's Study button follows it), as in the design. Double-click opens Anki's deck overview; the deck's ⋯ menu has **Open overview**; Esc on the overview returns Home. Settings ▸ "Clicking a deck" restores Anki's usual behaviour.

## [0.2.0] - 2026-10-24

### Added
- **Sidebar navigation** (on by default, "Sidebar navigation" in Settings): a left sidebar on Home, Overview and Stats with Decks, Stats, Browse, Add cards, Deck options (with shortcut hints), links other add-ons add to the toolbar, and Sync; plus a header with the screen title, a card search (opens the Browser; Ctrl+K focuses it) and Add card. Anki's top toolbar is hidden on these screens and comes back while reviewing. Narrow windows get an icon rail.
- **Statistics inside the main window** (sidebar, the T key and the toolbar's Stats link), with a Save PDF button. It uses the same trusted page type as Anki's Stats window, so Anki's security rules for the main window are unchanged. Turn the sidebar off to get the separate Stats window back.

## [0.1.0] - 2026-10-24

First installable build. Visual direction from the "Anki Revamp" design: warm neutrals, jade accent, Hanken Grotesk / Newsreader / JetBrains Mono (bundled, SIL OFL).

### Added
- Restyled deck list, deck overview, top toolbar, reviewer answer bar and Qt menus/scrollbars, following Anki's light and dark themes.
- Card browser: table, header and sidebar in the same palette (Anki's row, flag and selection colours are kept).
- The "finished this deck" screen, Statistics and Deck Options follow the palette and fonts (colours and fonts only; their layout is Anki's). Can be turned off separately.
- A Study button on each deck row with cards waiting; a welcome with create / import / shared-deck actions for a new, empty collection.
- Optional daily goal (cards per day) shown as progress in the Today panel.
- Optional, off by default: Japanese reading polish for card content (Japanese font for `lang="ja"` text, tidy furigana, furigana on hover / answer side). Zero-specificity rules, so note-type styling always wins.
- Home screen panels: cards-waiting headline with per-deck Study button and pace estimate, Today, 26-week Activity heatmap with current and best streak, and a Next 7 days forecast. All figures are read-only queries (manual and rescheduled review entries are excluded, matching Anki's own "studied today").
- Eight accent colours, comfortable and compact density, optional ease colours on answer buttons.
- Tools > Refine menu with a Settings dialog (live changes, reset to defaults) and a Diagnostics dialog.
- Per-screen switches and a master switch; a screen that raises an error is turned off automatically and logged.
- Log file at `user_files/logs/refine.log`.
- `scripts/build.py` produces a reproducible `.ankiaddon` with no top-level folder and validates it.
- Unit tests for configuration, theme tokens, guards, logging, home panels and packaging.

### Compatibility
- Anki Desktop 25.09 to 26.09.3. Tested on Windows only.
- Verified in Anki 25.09.5 and 26.09.3: all reviewer keyboard shortcuts and answer buttons behave as stock; the card area is pixel-identical to stock Anki (size and content, light and dark); settings apply live without re-rendering the reviewer.
- Verified alongside Migaku (which changes the answer buttons) and AnkiConnect.

### Notes
- Refine writes nothing to the collection and makes no network requests.


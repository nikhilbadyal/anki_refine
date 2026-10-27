# Changelog

All notable changes to Refine are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/) (0.x = beta).

## [0.3.2] - 2026-10-27

### Fixed
- **Updating from AnkiWeb failed on Windows** with "PermissionError: Access is denied … user_files … files_backup". Refine kept its log file open, and Windows won't let Anki rename the add-on's `user_files` folder while a file in it is open. The log file is now opened only while a line is written. If you are on 0.3.0 or 0.3.1, see the README ("Updating from 0.3.0 or 0.3.1") for the one-time workaround.

## [0.3.1] - 2026-10-27

### Changed
- The sidebar now shows your **profile name** at the top (with its first letter as the avatar) instead of "Anki" over the profile name. To change the name, rename the profile in Anki under File ▸ Switch Profile ▸ Rename.

### Fixed
- **Clicking a deck's name did nothing** in the deck list, for subdecks and top-level decks alike (clicking elsewhere on the row worked). It now selects the deck.
- **"N new left" no longer counts suspended new cards.** A deck whose only unseen card is suspended (for example a leech that was reset) showed "1 new left" even though nothing could be studied; it now shows just the leech badge.

## [0.3.0] - 2026-10-24

First public release (AnkiWeb and GitHub).

### Added
- **Light/Dark mode button** in the sidebar, above Sync. It switches Anki's own theme setting (the same as Preferences ▸ Theme).
- Licensed under the GNU AGPL v3, the same licence as Anki.

### Fixed
- Clicking Study on a deck with nothing left to study no longer leaves Anki's old top toolbar showing above the header on the "finished this deck" screen.

## [0.2.6] - 2026-10-24

### Added
- **Hover the Activity and Next 7 days panels** to see the figures for that day: "Today · 6 reviews", "Tue, Oct 20 · 14 reviews", "Tomorrow · 3 due". The label appears at once (no browser tooltip delay) and the square or bar under the pointer is highlighted.

### Changed
- **Full screen:** Home and the deck overview grow with large windows instead of staying a narrow centred column. Home widens to 1520px (1760px on very wide screens) with wider side panels; the overview widens with a taller 14-day chart.

### Fixed
- The header's Add card button keeps its dark primary style on the Stats screen.

## [0.2.5] - 2026-10-24

### Added
- **New cards left** under each deck in the list: how many new cards remain, the share already introduced and a thin progress line; with a steady pace, an estimate of when you'll finish (subdecks included).
- **Leech warning:** a small amber "N leeches" badge on decks with cards tagged *leech*; click it to open the Browser on exactly those cards.
- **Last 14 days chart** on the deck overview: a "Last 14 days" panel under the counts with stacked correct/Again bars, average reviews per day and percent correct for the deck and its subdecks. Setting: "Recent reviews chart on the deck overview".

## [0.2.4] - 2026-10-24

### Added
- **Retention column** in the deck list (as in the design): reviews remembered in the last 30 days, Anki's true-retention definition, including subdecks; amber below 85%, "—" with fewer than 20 reviews.
- **Session summary** on the "finished this deck" screen: today's cards, time and share of reviews correct, tomorrow's load and your streak, in one sentence.

### Fixed
- Header titles on the congrats and Stats screens use the interface font.

## [0.2.3] - 2026-10-24

### Changed
- **Home: click anywhere on a deck row to select it.** The headline then shows that deck's cards waiting, counts, time estimate and a Study button. With nothing selected it shows all decks combined; click empty space or press Esc to deselect.
- An **info button** (ⓘ) on each row opens the deck's overview (double-click still works).
- Expand/collapse is now a chevron instead of + / −.
- **Answer bar:** redesigned Again / Good buttons with the interval inside the button; only Again and Good are shown by default (keys 2 and 4 still answer Hard / Easy; Settings ▸ Reviewer to show all four).
- Accessibility (impeccable audit): secondary and faint text now meet WCAG AA contrast everywhere (live detector: 0 findings); selected rows marked without a side stripe and announced to screen readers; forecast labels enlarged; removed a sync dot that implied a status Refine can't know.


## [0.2.2] - 2026-10-24

### Changed (smoothness)
- Refine's styles and script are now built into each page instead of being downloaded from Anki's local server on every screen change (Anki doesn't let add-on files stay cached). Screen changes are now as fast as stock Anki.
- Selecting a deck is instant: the page updates in place instead of reloading.
- Home renders complete at once: the Today, Activity and Next 7 days panels reuse their last results and only re-query after something changed.
- No more grey flash between screens: the window paints Refine's background while Anki rebuilds a page.
- Statistics reopens faster (its page code is reused within a session).
- New **Motion** setting (default Smooth): gentle fade between screens with the sidebar staying still, soft hover transitions, panels fade when they update. Your system's reduced-motion setting still turns this off.

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


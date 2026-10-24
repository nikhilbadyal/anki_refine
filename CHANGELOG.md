# Changelog

All notable changes to Refine are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/) (0.x = beta).

## [0.1.0] - Unreleased

First installable build.

### Added
- Restyled deck list, deck overview, top toolbar, reviewer answer bar and Qt menus/scrollbars, following Anki's light and dark themes.
- Home screen panels: cards-waiting headline with per-deck Study button and pace estimate, Today, 26-week Activity heatmap with current and best streak, and a Next 7 days forecast. All figures are read-only queries (manual and rescheduled review entries are excluded, matching Anki's own "studied today").
- Eight accent colours, comfortable and compact density, optional ease colours on answer buttons.
- Tools > Refine menu with a Settings dialog (live changes, reset to defaults) and a Diagnostics dialog.
- Per-screen switches and a master switch; a screen that raises an error is turned off automatically and logged.
- Log file at `user_files/logs/refine.log`.
- `scripts/build.py` produces a reproducible `.ankiaddon` with no top-level folder and validates it.
- Unit tests for configuration, theme tokens, guards, logging, home panels and packaging.

### Compatibility
- Anki Desktop 25.09 to 26.09.3. Tested on Windows only.

### Notes
- Refine writes nothing to the collection and makes no network requests.


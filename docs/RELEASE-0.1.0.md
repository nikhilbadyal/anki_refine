# Refine 0.1.0: release readiness

Date: 2026-10-24. Package: `dist/refine-0.1.0.ankiaddon` (built by `py scripts/build.py`, ~196 KB, 50 entries). Git tag `v0.1.0` (local).

## Acceptance criteria (PLAN.md §14)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Installs from `.ankiaddon` on 25.09.x and 26.09.3 without errors | ✅ Windows | `devenv.py shots <target> --from-package` installs through Anki's own `AddonManager.install()` (`InstallOk Refine`). Full screenshot runs: 0 errors on 26.09.3 (official installer) and 25.09.5. macOS/Linux untested. |
| 2 | Screens render per design in light and dark, theme switch live | ✅ | `out/ui/*/{light,dark}_*.png`. Theme flips handled by Anki's classes plus the `style_did_init` filter, with no re-render (M0 F2). |
| 3 | Card area pixel-identical with Refine on/off | ✅ | `devenv.py verify`: card-webview grabs (question and answer, light and dark) hash IDENTICAL, size included, on 25.09.5 and 26.09.3. |
| 4 | Every listed shortcut behaves as stock | ✅ tested set | s, d, Space, 1, 3, Ctrl+1, *, e, -, Ctrl+Z, plus answer-button clicks: PASS with and without Refine. Not automated: m, r, =, !, @, v, o, i, Ctrl+Alt+*, Ctrl+Shift+D (Refine registers no shortcuts and does not touch the main webview's key handling). |
| 5 | Drag-reparent, collapse, gear menu, Shift-click, options work | ✅ (drag via command path) | E1–E4 PASS. Real mouse drag (jQuery UI) not automated; Refine keeps Anki's markup and handlers. |
| 6 | Collection unchanged by Refine | ✅ | E5: `col.mod`, max card/note mod and revlog count unchanged across browsing, Stats and settings toggles. All home queries are read-only `SELECT`s. |
| 7 | WCAG AA contrast for all token pairs | ✅ | `tests/unit/test_tokens.py` (8 accents × 2 themes × 2 densities). |
| 8 | Disabling a surface or the master switch restores stock look | ✅ | Live toggles verified (B.*); screenshots `B_e_no_deck_surface.png`, `B_f_disabled.png` match stock, including the JS-added Study buttons. |
| 9 | Injected exception → surface auto-disables, no Anki error dialog | ✅ | E6: surface disabled after 3 errors, page renders stock, no dialog, errors logged. |
| 10 | Start-up ≤ 50 ms; render overhead small | ✅ | 16 ms warm / 52 ms cold (log). Home stats 0.2–9 ms in a background QueryOp on real collections. Deck-browser render overhead not separately measured. |
| 11 | Migaku and AnkiConnect coexist | ◐ | Migaku: screenshot runs with the user's Migaku copy, 0 errors (Migaku's 2-button reviewer styled correctly). AnkiConnect not run alongside (its HTTP port would clash with the user's running Anki). |
| 12 | `.ankiaddon` valid, AnkiWeb-acceptable | ◐ | `build.py --check`: no top-level folder, no pycache, relative paths; installs via Anki's validator. Not yet uploaded to AnkiWeb. |
| 13 | README covers install, config, troubleshooting, rollback, compat | ✅ | README.md, config.md, CHANGELOG.md. |

## Test totals

- Unit and contract tests: `py -m unittest discover -s tests -t .`, 94 tests, all pass.
- Behaviour suite: `py scripts/devenv.py verify <target> [--without-refine]`: 43 / 43 PASS on 26.09.3 (installer) and 25.09.5.
- Visual suite: `py scripts/devenv.py shots <target> [--colpkg backup] [--from-package file]`: deck list, overview, reviewer, menu, browser, settings, diagnostics, stats, deck options, congrats, empty collection, real-data copies of both user profiles.

## Known limitations

- Windows only tested. macOS and Linux need a run before claiming support.
- Interface strings are English only.
- Stats and Deck Options keep Anki's layout and its blue primary/toggle colours (compiled Bootstrap). Only colours and fonts change.
- Real mouse drag-and-drop of decks is not automated.
- A surface auto-disabled after errors stays off until Anki restarts.

# M0 report: verification spike

Date: 2026-10-24 · Status: **complete. All five open questions are answered with runtime evidence.**
Raw data: [M0-RESULTS.md](M0-RESULTS.md) (generated) and `tests/contract/fixtures/<target>/` (snapshots, `probe.json`, `cdp.json`).

## What was built

| Deliverable | Where | Verified by |
|---|---|---|
| Git repository, layout per PLAN §8 | `src/refine/`, `devtools/`, `scripts/`, `tests/`, `docs/` | `git init`; the tree matches the plan |
| M0 add-on skeleton (web exports only, no hooks) | `src/refine/` | Loads on all targets; `/_addons/refine/web/css/base.css` → 200, non-exported `config.json` → 404 |
| Version environments | `.venv/anki-25.9.5`, `.venv/anki-26.9.3` (`devenv.py venvs`) | Exact PyQt/QtWebEngine pins of each release (see finding F1) |
| Isolated dev profiles | `.anki-dev/<target>/` (`devenv.py setup`) | Probe refuses to run outside `.anki-dev`; your own Anki (PID 8904) kept running untouched during all 4 rounds |
| Linked add-on install | NTFS junctions `addons21/refine` → `src/refine`, `addons21/refine_m0_probe` → `devtools/m0_probe` | `--fresh` reset removes the links without following them into the source tree |
| Webview debugging | `QTWEBENGINE_REMOTE_DEBUGGING` (`devenv.py run <target> --port 8080`) | `/json/version` and `/json/list` reachable on every target; pages "main webview", "top toolbar", "bottom toolbar" |
| Automated HTML snapshots | `devtools/m0_probe` + `devenv.py snapshot --all` | 11 screens × 3 targets, unattended, about 33 s per target, exit code 0, 0 probe errors, 4 consecutive rounds |
| Selector contract tests | `tests/contract/test_selectors.py` (44 selectors), `tests/unit/` | 8/8 pass; a mutated fixture fails with the exact version/screen/selector |

Targets exercised: **26.09.3-installed** (your official install), **26.09.3-pypi**, **25.09.5-pypi**.

---

## The five questions

### Q1: Which Chromium runs in the webviews, and which CSS can we use?

| | 25.09.5 | 26.09.3 (installer and PyPI identical) |
|---|---|---|
| Qt / PyQt | 6.9.1 / 6.9.1 | 6.11.2 / 6.11.0 |
| QtWebEngine | 6.8.2 | 6.11.2 |
| Chromium | **122.0.6261.171** | **140.0.7339.225** |

Every feature tested works on both: `@layer` (applies, and loses to unlayered rules as the cascade spec says), `:where`, `:is`, `:has`, `:focus-visible`, `color-mix()`, `oklch()`, container queries, CSS nesting, `mask-image`, `text-wrap: balance`, `ruby-position`, `scrollbar-gutter`, `accent-color`.

**Decision.** The CSS baseline is Chromium 122, and the plan's approach of `@layer` plus `:where()` is confirmed.
- **Caveat:** `aqt` 25.09 also ships optional `qt66` / `qt67` / `qt68` extras for users who picked an older Qt in the 25.09 launcher (Qt 6.6 ≈ Chromium 112). These were not tested.
- **Shipped CSS:** avoids nesting and `text-wrap: balance`, both of which are newer than Chromium 112. Shipped CSS is written flat, and those features are progressive enhancement only.
- **Diagnostics:** 26.09's user agent is reduced to `Chrome/140.0.0.0`, so read the version with `qWebEngineChromiumVersion()`, not the user agent.

### Q2: Do the legacy class names differ between 25.09 and 26.09?

**No.** The class/id/data-attribute inventory is identical across 25.09.5 and 26.09.3 for the deck browser (before and after review, light and dark), its bottom bar, the toolbar, the overview and its bottom bar, and the reviewer bottom bar (question and answer). The only difference is `#MJX-CHTML-styles` in 25.09's reviewer, because 26.09 lazy-loads MathJax, as its release notes say.

Confirmed hooks into the DOM, now enforced by `test_selectors.py`:
- **Deck browser:** `tr.deck`, `tr.deck.current`, `tr.top-level-drag-row`, `td.decktd`, `a.deck`, `a.deck.filtered`, `a.collapse`, `th.count`, `td.opts`, `img.gears`, `span.new-count`, `span.learn-count`, `span.review-count`, `span.zero-count`, `#studiedToday`.
- **Toolbar:** `a.hitem`, `#decks`, `#add`, `#browse`, `#stats`, `#sync`, `.left-tray`, `.right-tray`.
- **Overview:** `button#study`, plus the three count spans and `.bury-count`.
- **Reviewer:** `body.card.card1`, `#qa`, `#_mark`, `#_flag`.
- **Reviewer bottom bar:** `button#ansbut`, `#time`, `td.stat`, `button[data-ease=1…4]`, `button#defease`, `span.nobold`.

Avoid targeting `ui-draggable` / `ui-droppable`. jQuery UI adds them at runtime, so they are not part of Anki's markup.

### Q3: How does the top toolbar's height react to taller CSS?

The toolbar is a webview with a **fixed Qt height** (37 px here). It is measured from `document.documentElement.offsetHeight` only when `Toolbar.draw()` runs: `stdHtml()` followed by `adjustHeightToFit()`.

| How +32 px of padding is added | Widget height | Result |
|---|---|---|
| Via `webview_will_set_content` at render time (`Toolbar.draw()`) | 37 → **69** | correct, nothing clipped |
| Injected later by JS | stays **37** | **clipped** |
| …then `mw.toolbar.web.adjustHeightToFit()` | → **69** | correct |
| Removed, then `adjustHeightToFit()` / `draw()` | → 37 | restored |

`Toolbar.redraw()` does **not** re-render: it only refreshes sync state and fires `top_toolbar_did_redraw`. `Toolbar.draw()` does re-render.

**Decision.** The plan's "±4 px" restriction is dropped. Toolbar CSS is delivered through `webview_will_set_content`. On a live settings change, inject the new style and call `mw.toolbar.web.adjustHeightToFit()`. That is a public, but undocumented, `AnkiWebView` method, so wrap the call in the error guard. Untested: the "hide top bar while reviewing" mode, which animates the height separately (`toolbar.py:219-270`). Test it in M2.

### Q4: What exactly is `col.sched.day_cutoff`?

- An `int` of **epoch seconds** for the **start of the next scheduler day**. That is the next local occurrence of the rollover hour (tested: rollover 4 → `2026-10-25T04:00+05:30`). It matched an independent computation on all targets.
- It follows a rollover change **immediately**. Rollover 4 → 10 moved the cutoff to 10:00 the same day, and it was restored afterwards.
- Anki's own "studied today" ([rslib `studied_today`](https://github.com/ankitects/anki/blob/26.09.3/rslib/src/storage/revlog/mod.rs) + `studied_today.sql`) uses `revlog.id > (next_day_at − 86400) × 1000 AND type NOT IN (4 Manual, 5 Rescheduled)`. The probe saw exactly this: 2 revlog rows today (one Manual row from `set_due_date` during seeding, one real review) against Anki's "Studied 1 card in 3.91 s". With the type filter, the figures match.

**Decision for the V1 dashboard.** Use Anki's formula exactly: strict `>`, the same −86400 offset, so DST-day behaviour matches Anki's, and exclude types 4 and 5. Refresh on `day_did_change`, which exists in both versions.

### Q5: Is there a public way to refresh the reviewer's styling?

| Path | Re-runs content hook | Side effect on the card being reviewed |
|---|---|---|
| JS `<style>` swap via `web.eval()` | no | **none**: applied instantly in both reviewer webviews |
| `mw.reviewer.refresh_if_needed()` | no | none (no-op unless something is pending) |
| `mw.reset()` (legacy) | no | marks queues dirty. **If the window is focused** it rebuilds and re-shows the question, so the revealed answer is lost (`reviewer.py:221-233`). Seen in the focused runs, not in the unfocused ones |
| `mw.moveToState("review")` | **yes** (Reviewer, ReviewerBottomBar) | same card, but flips back to the **question** |

**Decision.** There is no side-effect-free re-render API, and none is needed. Live settings changes swap a `<style id="rf-…">` in each open webview through `eval()`. New renders get the CSS through `webview_will_set_content`. Never call `mw.reset()`. Use `moveToState("review")` only while the question side is showing.

---

## Further findings (not among the five, but they change the plan)

- **F1. The editor-setup docs' `pip install aqt[qt6]` is wrong.** No such extra exists, so pip silently installs the newest PyQt6, and you end up "testing 25.09" on Chromium 140. Use `aqt[qt]`.
- **F2. The `style_did_init` start-up gap is confirmed at runtime.** There are 0 calls before or at start-up, then exactly one per theme change. Webviews flip `html.night-mode` without re-rendering (the content-hook count is unchanged across a flip). So: insert our QSS directly at start-up, then let the filter handle theme changes (PLAN §7.3).
- **F3. `reduce_motion` defaults to True** (`profiles.py:543`), and fresh profiles carry `body.reduce-motion`. Most users will see **no** transitions unless they turn the preference off. Motion must be purely decorative, and the design must not depend on it.
- **F4. Unattended runs need a pre-seeded profile.** On first start, Anki opens a modal language chooser that `-l en` does not skip (`profiles.py:466`). `devenv.py` seeds `prefs21.db` with Anki's own `ProfileManager`.
- **F5. Single-instance isolation.** 26.x honours `ANKI_SINGLE_INSTANCE_KEY`. 25.09 doesn't, but derives its key from `getpass.getuser()`, so `LOGNAME` is set per dev instance.
- **F6.** A request for a non-exported add-on file is logged to the console ("couldn't locate item in add-on folder") and returns 404. That gives an easy diagnostic for a mis-set web-export pattern.

## Not covered by M0 (carried forward)

- Linux and macOS. Everything ran on Windows 11 only.
- 25.09's optional older-Qt builds (`qt66`–`qt68`).
- Toolbar auto-hide in review mode (M2).
- AnkiWeb rollback/branch behaviour (M5, PLAN §13).
- Screen-reader baseline of stock Anki (M5).

## Recommendation

The foundation holds and no assumption in the architecture was falsified. Three plan details changed: the toolbar rule, the live-update mechanism, and motion defaults. They are already applied to PLAN.md. **Proceed to M1 (core foundation).**

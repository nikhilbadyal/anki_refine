# PLAN — Modern UI Enhancement Add-on for Anki Desktop

> Working title: **Refine** (package folder `refine/`). The name is a placeholder; see Open Questions.
> Status: planning only. Nothing in this document has been implemented.
> Prepared: 2026-10-24. Target: Anki **26.09.3** (latest stable; installed on the dev machine).

Evidence tags used throughout:

- **[SRC]** — verified by reading Anki 26.09.3 source (`git clone --branch 26.09.3 ankitects/anki`, files under `qt/aqt/`, `qt/tools/`, `ts/lib/sass/`).
- **[LOCAL]** — verified on this machine's Anki 26.09.3 install (`%LOCALAPPDATA%\Programs\Anki\app_packages`).
- **[DOC]** — stated in official add-on docs (docs.ankiweb.net/addons, formerly addon-docs.ankiweb.net) or release notes.
- **[UNVERIFIED]** — plausible but must be confirmed in a running Anki before relying on it.

---

## 1. Executive summary

**What we are building:** an Anki Desktop add-on that restyles Anki's existing screens into a coherent, modern design system (light and dark), with small, opt-in usability improvements. Anki keeps doing all of the scheduling, data, sync, and card rendering.

**Recommended direction: restyle, don't replace.**

The core principle comes from what is already on the market. The most active competitor, Onigiri (GPL-3.0, last commit 12 Oct 2026), replaces Anki's deck browser and overview rendering by assigning over internal methods (`DeckBrowser._renderPage`, `DeckBrowser._render_deck_node`, `Overview._table`, `Overview._body`). Anki Redesign, the previous lightweight option, has not been updated since early 2023 and its installed copy declares `max_point_version: 250902`. Migaku, another popular add-on, also overwrites `Reviewer` methods. Any add-on that replaces the same functions conflicts with these.

This add-on will instead:

1. Use **only public `gui_hooks`** for integration. No method replacement in MVP or V1.
2. **Keep Anki's DOM and Python-generated HTML intact** in the webview screens, and restyle them with scoped CSS built on Anki's own design tokens (`--fg`, `--canvas-elevated`, `--border-subtle`, `--state-new`, …).
3. Restyle **Qt widget surfaces** (menus, scrollbars, browser table, dialogs) through the sanctioned `gui_hooks.style_did_init` filter, kept conservative and individually switchable.
4. **Leave card content alone by default.** Card templates own their typography. Optional card-level enhancements, such as CJK/Japanese typography and ruby styling, are opt-in and use zero-specificity selectors so any template rule wins.
5. **Fail closed.** Every surface is an isolated module wrapped in error guards. If one fails, it disables itself, logs the error, and leaves Anki's default look for that surface.

**Is a single add-on enough?** Yes for application chrome, the deck browser, the overview, the reviewer frame and buttons, the toolbars, and Qt widgets. Two parts can only be done in a limited way:
- **Card content.** It is defined by each note type's template. We can offer an opt-in "typography layer" but cannot guarantee a result on arbitrary templates. Template-level changes, such as a better Japanese vocabulary layout, would ship as *optional, separately installable note-type templates* (Future), never as automatic modifications.
- **SvelteKit pages.** These include deck options, statistics, preferences, card info, the congrats screen, import, change-notetype, and the experimental editor. They load by URL and bypass `webview_will_set_content`. We can only append CSS after load via `webview_did_inject_style_into_page`, and their internal class names are unstable build output. They get **token-level theming only** (accent color, radii), in V1, behind an "experimental" flag.

**MVP in one line:** design tokens + theme engine, then restyled deck browser, overview, reviewer bottom bar and answer buttons, and top toolbar, plus conservative Qt menu, scrollbar, and focus styling, a settings dialog with reset, and a per-surface kill switch. All of it is hooks-only and tested on 25.09 → 26.09.3.

---

## 2. Requirements

### 2.1 Functional requirements

| ID | Requirement |
|---|---|
| F1 | Restyle the deck browser, overview, reviewer chrome (bottom bar, answer buttons, mark/flag indicators, type-answer input, audio replay buttons), and top/bottom toolbars in light and dark themes. |
| F2 | Follow Anki's own theme setting (Light/Dark/Follow System) and update live on `theme_did_change`, with no restart and no reload flash. |
| F3 | Accent color selection from a curated palette with guaranteed contrast. Custom hex input is accepted only if it passes a contrast check. |
| F4 | Interface density (Comfortable/Compact) and interface font-family choice for add-on-styled surfaces. Card fonts are untouched unless the card layer is enabled. |
| F5 | Per-surface on/off toggles, a global on/off toggle, and "Reset to defaults". |
| F6 | Settings UI reachable from Tools ▸ Add-ons ▸ Config (via `setConfigAction`) and a Tools-menu entry. |
| F7 | All existing keyboard shortcuts keep working exactly as before. New shortcuts must not collide with Anki's (see §6.3). |
| F8 | Optional, opt-in card typography layer, including CJK font fallback and ruby/furigana styling. |
| F9 (V1) | "Today" summary strip on the deck browser: reviews and time today, cards still due, optional daily goal, and study streak. |
| F10 (V1) | Restyle the Qt browser window (table, sidebar, search bar) and common dialogs. |

### 2.2 Non-functional requirements

| ID | Requirement |
|---|---|
| N1 | **Zero data writes** to the collection in MVP. V1 writes nothing to the collection either: the goal and streak settings live in add-on config, not `col.conf`. |
| N2 | No modification of Anki's installed files. No dependencies beyond what Anki bundles (Python stdlib, PyQt6 via `aqt.qt`). |
| N3 | Public hooks only. No monkey-patching in MVP/V1. Any future exception lives in `refine/compat/experimental/`, off by default, and version-gated. |
| N4 | An exception in any add-on code path must never propagate into Anki. The surface disables itself for the session after repeated errors. |
| N5 | Startup overhead under 50 ms added to Anki's startup, and per-render overhead under 5 ms on the deck browser, measured on a 50k-card collection (see §10.6). |
| N6 | Dashboard queries run off the UI thread (`QueryOp`) and are bounded (date-windowed, indexed). |
| N7 | WCAG 2.2 AA contrast (4.5:1 text, 3:1 UI components) for every token pair in both themes, enforced by an automated test. |
| N8 | Respect Anki's "Reduce motion" preference (`reduce-motion` body class [SRC]) and `prefers-reduced-motion`. |
| N9 | Works at 100–200% display scaling and at window widths from 800 px to ultrawide. |
| N10 | Python 3.9-compatible syntax (25.09 still allows 3.9; 26.05+ requires ≥ 3.10; official builds ship 3.13 [DOC]). |
| N11 | License compatible with AnkiWeb (AGPL-3.0-compatible required) — recommend **AGPL-3.0-or-later**. |

---

## 3. Technical findings

### 3.1 Versions on the target platform

| Item | Value | Evidence |
|---|---|---|
| Anki | 26.09.3 (released 23 Sep 2026; marked "Latest", security fixes) | [LOCAL] `aqt-26.9.3.dist-info`; [release notes](https://github.com/ankitects/anki/releases/tag/26.09.3) |
| Python | 3.13 bundled (`python313.dll`); minimum supported 3.10 since 26.05 | [LOCAL]; [26.05 notes](https://github.com/ankitects/anki/releases/tag/26.05) |
| PyQt6 / Qt | PyQt6 6.11.0, Qt 6.11.2, PyQt6-WebEngine 6.11.0 | [LOCAL]; [26.09 notes](https://github.com/ankitects/anki/releases/tag/26.09) |
| Qt5 | Removed entirely in 25.07 | [25.07 notes](https://github.com/ankitects/anki/releases/tag/25.07) |
| Version int | `anki.utils.int_version()` → `YYMMPP` (26.09.3 → `260903`) | [SRC] `pylib/anki/utils.py` |

Upgrade-path caveat: auto-update from 25.07–25.09 to 26.05+ is not supported because of installer changes ([26.05](https://github.com/ankitects/anki/releases/tag/26.05), [26.08](https://github.com/ankitects/anki/releases/tag/26.08)). A significant share of users is therefore likely still on **25.09.x**. This is the main reason the compatibility floor is set at 25.09 (§11).

### 3.2 Which technology implements each screen

| Screen | Technology | How it is built | Customization route |
|---|---|---|---|
| Main window frame, menu bar, splitter | Qt widgets | `aqt/main.py`, `forms/main.ui` | Qt stylesheet via `style_did_init` [SRC] |
| Top toolbar (Decks/Add/Browse/Stats/Sync) | QtWebEngine, legacy HTML | `aqt/toolbar.py` `TopToolbar`, `stdHtml(..., css=["css/toolbar.css"])` [SRC] | `webview_will_set_content` (context `TopToolbar`), `top_toolbar_did_init_links`, tray hooks |
| Deck browser | QtWebEngine, legacy HTML | Python builds a `<table>` string (`_renderDeckTree`); `DeckBrowserContent(tree, stats)` [SRC] | `webview_will_set_content` (context `DeckBrowser`), `deck_browser_will_render_content`, `deck_browser_did_render` |
| Deck browser bottom bar | QtWebEngine | `BottomBar.draw(..., web_context=DeckBrowserBottomBar)` [SRC] | `webview_will_set_content` (context `DeckBrowserBottomBar`) |
| Deck overview | QtWebEngine, legacy HTML | `OverviewContent(deck, shareLink, desc, table)` [SRC] | `webview_will_set_content` (context `Overview` / `OverviewBottomBar`), `overview_will_render_content` |
| Congrats screen | **SvelteKit page** | `load_sveltekit_page("congrats")` [SRC] | Post-load CSS only (`webview_did_inject_style_into_page`) |
| Reviewer (card area) | QtWebEngine | `revHtml()`: `<div id="qa">` + `reviewExtra`; card HTML from the note type template; body classes `card cardN` [SRC] | `webview_will_set_content` (context `Reviewer`), `card_will_show` filter, `reviewer_did_show_question/answer` |
| Reviewer bottom bar / answer buttons | QtWebEngine, legacy HTML | `<button data-ease="N" onclick='pycmd("easeN")'>` inside a `<table>` [SRC] | `webview_will_set_content` (context `ReviewerBottomBar`), `reviewer_will_init_answer_buttons` |
| Browser (card/note list, sidebar) | Qt widgets (`QTableView`, `QTreeView`) | `aqt/browser/` [SRC] | Qt stylesheet (`style_did_init`), `browser_will_show` |
| Browser editor panel | Legacy webview editor by default; SvelteKit "experimental editor" if `ExperimentFlag.SVELTE_EDITOR` is on (26.08+) | `browser.py:619` [SRC] | Out of scope for MVP (in flux upstream) |
| Add / Edit Current | Legacy editor by default (`addcards_legacy`, `editcurrent_legacy`) | [SRC] | Out of scope for MVP |
| Deck options, Statistics, Preferences, Card info, Import, Change notetype | **SvelteKit pages** | `load_sveltekit_page(...)` [SRC] | Post-load CSS only; tokens only, V1 experimental |
| Card layout, previewer, dialogs (Add-ons, Profiles, About…) | Mostly Qt widgets + embedded webviews | [SRC] | Qt stylesheet; webview contexts where present |

Not everything can be restyled with CSS. Qt-widget screens need Qt Style Sheets (QSS), which is a CSS-like subset with no variables, no `:has`, and limited animation. The SvelteKit pages are compiled Svelte output whose class names are hashed or unstable.

### 3.3 Public APIs and hooks relevant to this add-on

All hook names below exist in 26.09.3's `qt/tools/genhooks_gui.py` [SRC]. The complete list was extracted, and the full hook definitions are in [genhooks_gui.py @ 26.09.3](https://github.com/ankitects/anki/blob/26.09.3/qt/tools/genhooks_gui.py).

| Purpose | Hook / API | Type | Notes |
|---|---|---|---|
| Add CSS/JS/head to legacy webviews | `gui_hooks.webview_will_set_content(web_content, context)` | hook (mutates `WebContent`) | Fires from `AnkiWebView.stdHtml` only [SRC]. `context` identifies the screen (DeckBrowser, Overview, Reviewer, *BottomBar, TopToolbar…). Docs: [hooks-and-filters](https://docs.ankiweb.net/addons/hooks-and-filters) |
| Serve add-on files to webviews | `mw.addonManager.setWebExports(__name__, r"web/.*\.(css|js|svg|woff2)")` → `/_addons/<pkg>/web/...` | API | [SRC] `addons.py:767`; docstring in `webview.py:324-373` |
| Style SvelteKit pages after load | `gui_hooks.webview_did_inject_style_into_page(webview)` + `webview.kind` (`AnkiWebViewKind`) | hook | Fires after Anki's own dynamic styling on `load_ts_page`/`load_sveltekit_page` pages [SRC `webview.py:910-930`] |
| Global Qt stylesheet | `gui_hooks.style_did_init(buf) -> str` | **filter** | Called inside `ThemeManager._apply_style` on every theme/style change [SRC `theme.py:276`] |
| Theme changes | `gui_hooks.theme_did_change()` | hook | Webviews already toggle `html.night-mode`, `body.nightMode/night_mode` themselves [SRC `webview.py:989`] |
| Theme state | `aqt.theme.theme_manager.night_mode`, `.var(colors.X)`, `.qcolor()`, `.body_class()` | API (public module attribute, not formally documented) | [SRC] |
| Body-class refresh | `gui_hooks.body_classes_need_update()` | hook | Anki toggles `fancy` / `reduce-motion` [SRC] |
| Deck browser content | `deck_browser_will_render_content(deck_browser, content)`, `deck_browser_did_render` | hooks | Append-only usage planned |
| Overview content | `overview_will_render_content`, `overview_did_refresh`, `overview_will_render_bottom` | hooks | |
| Reviewer | `reviewer_did_show_question`, `reviewer_did_show_answer`, `reviewer_did_answer_card` | hooks | Used. `card_will_show` and `reviewer_will_init_answer_buttons` are deliberately **not** used (we don't rewrite card HTML or button lists; see §3.9). [Reviewer JavaScript doc](https://docs.ankiweb.net/addons/reviewer-javascript) |
| Toolbar | `top_toolbar_did_init_links`, `top_toolbar_will_set_left/right_tray_content`, `top_toolbar_did_redraw` | hooks | |
| JS → Python | `webview_did_receive_js_message(handled, message, context)` with `pycmd("refine:...")` | filter | Must return `(False, None)`-style passthrough for messages that aren't ours |
| Lifecycle | `main_window_did_init`, `profile_did_open`, `profile_will_close`, `collection_did_load`, `state_did_change`, `operation_did_execute`, `sync_did_finish`, `day_did_change` | hooks | |
| Config | `mw.addonManager.getConfig/writeConfig/setConfigAction/setConfigUpdatedAction` | API | [addon-config doc](https://docs.ankiweb.net/addons/addon-config) |
| Background reads | `aqt.operations.QueryOp(parent, op, success).run_in_background()` | API | [background-ops doc](https://docs.ankiweb.net/addons/background-ops) |
| Due counts | `col.sched.deck_due_tree()`, `col.studied_today()` | API | Same calls Anki's deck browser uses [SRC `deckbrowser.py:163`] |
| Profile preferences | `mw.pm.minimalist_mode()`, `mw.pm.reduce_motion()`, `mw.pm.uiScale()`, `mw.pm.theme()` | API (internal-ish) | [SRC `profiles.py:535-615`] — read-only use |

**Documented vs internal:**
- *Documented public:* `gui_hooks.*`, `setWebExports`, `getConfig`/`writeConfig`/`setConfigAction`, `QueryOp`/`CollectionOp`, `mw.col` methods, `aqt.qt` imports.
- *Public but undocumented, used read-only:* `theme_manager`, `aqt.colors`, `AnkiWebViewKind`, `mw.pm.*` getters, DOM structure and CSS class names of legacy screens (`.deck`, `.new-count`, `#qa`, `[data-ease]`, `#defease`, `#ansbut`).
- *Internal, not to be used:* `DeckBrowser._render*`, `Overview._table/_body`, `Reviewer._initWeb/_answerCard/_bottomHTML`, `ThemeManager._apply_style`, anything prefixed `_`.

The DOM/class-name contract is the main fragile dependency. It is tracked by an automated "selector contract" test (§10.2).

### 3.4 Add-on loading, initialization, and cleanup

- Anki imports each `addons21/<folder>/__init__.py` at startup, **before any profile or collection is loaded** [DOC [the-anki-module](https://docs.ankiweb.net/addons/the-anki-module)]. So `__init__.py` only registers hooks and touches no collection.
- Folder name = AnkiWeb ID for AnkiWeb installs; `meta.json` (managed by Anki) stores the enabled state and the user's edited config. `user_files/` survives upgrades; **every other file is deleted on upgrade** [DOC [addon-folders](https://docs.ankiweb.net/addons/addon-folders), [addon-config](https://docs.ankiweb.net/addons/addon-config)].
- Per-screen state is driven by `state_did_change` and the hooks above. Teardown: `profile_will_close` (flush caches; nothing to persist into the collection). Hook handlers are removed with `.remove()` when a surface is disabled at runtime [DOC hooks-and-filters].
- Anki itself removes webview hook subscriptions on webview destroy (26.09 "Unhook AnkiWebView when destroyed" [release notes](https://github.com/ankitects/anki/releases/tag/26.09)).
- Safe mode: holding **Shift** at startup, or `--safemode`, disables all add-ons [SRC `aqt/__init__.py:346-497`]. This is the universal rollback lever documented to users.

### 3.5 Scoped injection without affecting unrelated screens

- `webview_will_set_content` gives a `context` object. We register **per-context** stylesheets (`isinstance(context, DeckBrowser)` etc.) and never inject unconditionally. Unknown contexts (other add-ons' webviews) get nothing.
- Every rule is prefixed with a root guard class (`html.refine`) set by a tiny head script. Turning a surface off only needs a class toggle, and other add-ons' DOM is never targeted.
- CSS is wrapped in `@layer refine { … }`, so un-layered author CSS from Anki, card templates, or other add-ons wins by cascade order. Card-area rules additionally use `:where()` (zero specificity). **Verified in M0:** 25.09.5 runs Chromium 122 and 26.09.3 runs Chromium 140. `@layer`, `:where`, `:has`, `color-mix`, `oklch`, and container queries all work, and layered rules lose to unlayered ones as intended ([M0 report Q1](docs/M0-REPORT.md)). Shipped CSS avoids nesting and `text-wrap: balance`, because 25.09's optional older-Qt builds (Chromium ~112) were not tested.
- Dynamic values (accent, density, fonts) are emitted as a small `<style>` of CSS custom properties in `web_content.head`. Static rules are served from `web/` via web exports, so they are cacheable and diffable.
- Qt: QSS is appended inside a marked block `/* refine:begin */ … /* refine:end */` in the `style_did_init` filter. Rules target Qt class names, plus `objectName` where stable, and never set global `QWidget` properties.

### 3.6 Configuration and persistence

- `config.json` (defaults) + `config.md` (docs). Anki stores user edits in `meta.json` [DOC]. A `schema_version` key enables migrations, and missing keys fall back to defaults in code (not only in Anki's merge). This is because changing defaults in `config.json` does not update users who already edited their config [DOC].
- Keys must not start with `_` (reserved by Anki) [DOC].
- Add-on config is **global across profiles**. Per-profile values, such as the daily goal, are stored as `profiles: {<name>: {...}}` inside config. Nothing is written to `col.conf`, so nothing syncs and nothing touches collection integrity.
- Runtime config changes (from our dialog, or `setConfigUpdatedAction` for the JSON editor) re-apply styles live: webviews are refreshed through the screen's own `refresh()`, and QSS through the marked-block replacement (§7.4).

### 3.7 Light and dark themes

- Anki resolves Light/Dark/System in `ThemeManager._determine_night_mode` and then calls `theme_did_change` [SRC]. Web pages get `html.night-mode` and `data-bs-theme="dark"`; Anki's tokens switch via `:root[class*=night-mode]` [SRC `webview.py:688`].
- **We do not add a separate theme switch.** Our tokens are defined for `:root` and `:root.night-mode`, so they follow Anki's setting automatically. Qt QSS is regenerated because `style_did_init` runs on every `_apply_style` call.
- Anki's own token vocabulary [SRC `ts/lib/sass/_vars.scss`]: `--fg`, `--fg-subtle`, `--fg-disabled`, `--fg-faint`, `--fg-link`, `--canvas`, `--canvas-elevated`, `--canvas-inset`, `--canvas-overlay`, `--canvas-code`, `--canvas-glass`, `--border`, `--border-subtle`, `--border-strong`, `--border-focus`, `--button-*`, `--shadow*`, `--accent-card/note/danger`, `--state-new/learn/review/buried/suspended/marked`, `--highlight-*`, `--selected-*`, `--border-radius` (5px), `--border-radius-medium` (12px), `--transition` (180ms). We **map our tokens onto these** where they exist, so pages we don't fully restyle still blend.

### 3.8 Handling API changes across releases

- `refine/compat/version.py` reads `int_version()` once. Each surface declares `min_version`/`max_tested`. On untested newer versions, surfaces still run but the guarded wrappers make failures safe.
- **Hook-existence check at startup:** each surface lists the hooks it needs, and is skipped with a logged note if any is missing (`hasattr(gui_hooks, name)`).
- **Selector contract:** each surface lists the DOM selectors it relies on. In debug builds, a JS probe reports missing selectors through `pycmd`, and CI runs the same check against fixtures (§10.2).
- Track upstream: watch [ankitects/anki releases](https://github.com/ankitects/anki/releases) and diff `genhooks_gui.py`, `deckbrowser.py`, `overview.py`, `reviewer.py`, `toolbar.py`, and `ts/lib/sass/_vars.scss` for each beta.
- Upstream signal: Anki's lead developer has called `deckbrowser`/`reviewer` "old code in need of an update" ([forum, 2021](https://forums.ankiweb.net/t/implementing-redesign-add-on-into-ankis-base-code/12831)). The June 2026 team update announced an add-on system revamp with no details ([forum](https://forums.ankiweb.net/t/updates-from-the-anki-team-june-2026/70120)). Expect these screens to be rewritten eventually. The CSS-over-existing-DOM approach keeps our sunk cost per screen small.

### 3.9 Not breaking sync, reviewing, scheduling, or integrity

- The add-on never writes to the collection: no `col.db.execute`, no `update_card`/`update_note`, no `col.conf` writes. Direct DB writes don't sync and schema changes are forbidden [DOC the-anki-module].
- Dashboard reads use `QueryOp` (serialized with other collection operations, off the main thread) and read-only `SELECT`s on `revlog`. No Qt calls inside the op [DOC background-ops].
- Reviewer integrity: we never change `pycmd("easeN")` / `pycmd("ans")` handlers, button order, or count. `reviewer_will_init_answer_buttons` is **not** filtered by us (Migaku and others use it). We style whatever buttons exist via `[data-ease]`.
- No interference with `card_will_show` output in MVP. The V1 card layer only adds a class to `<body>` via JS in `reviewer_did_show_question`, not HTML rewriting.

### 3.10 Diagnosing add-on conflicts

- **Conflict surfaces on this very machine** [LOCAL]: Migaku (`1846879528`) overwrites `Reviewer._linkHandler`, `Reviewer.revHtml`, `Reviewer._answerCard` and wraps `Reviewer._initWeb`. AnkiConnect (`2055492159`) uses editor/browser hooks only. Anki Redesign (`2119814566`) is installed but disabled.
- Built-in diagnostics (V1): "Refine ▸ Diagnostics…" shows Anki/Qt/Chromium versions, enabled surfaces, surfaces auto-disabled after errors, the other enabled add-ons, and a log excerpt, with "Copy report".
- **Bisect procedure** (documented in README): (1) Shift-start to confirm an add-on is involved; (2) disable Refine surfaces one by one from settings; (3) disable other add-ons by halves.
- Webview inspection: `QTWEBENGINE_REMOTE_DEBUGGING=8080` then open `http://localhost:8080` in Chrome [DOC [debugging](https://docs.ankiweb.net/addons/debugging)]. Console output: `anki-console.bat` on Windows [DOC console-output].
- Logging uses Python `logging` under the add-on's logger. Nothing is printed to stderr in normal operation, because Anki pops stderr output up as an error dialog [DOC debugging]. Anki 26.09 attaches a handler to each add-on's root logger ([release notes](https://github.com/ankitects/anki/releases/tag/26.09)). Whether that gives a file log for free is **[UNVERIFIED]**, so we also keep a small rotating log in `user_files/logs/`.

### 3.11 Packaging and distribution

- `.ankiaddon` = zip of the add-on folder's *contents* (no top-level folder), with no `__pycache__` [DOC [sharing](https://docs.ankiweb.net/addons/sharing)]. Upload at https://ankiweb.net/shared/addons.
- `manifest.json` (`package`, `name`, optional `conflicts`, `mod`) is needed for non-AnkiWeb (GitHub) installs [DOC].
- Version gating: `min_point_version` / `max_point_version`. A *negative* max is a hard cap; a positive max is informational [SRC `addons.py:129-136`]. We use `min_point_version: 250900` and positive `max_point_version` = highest tested.
- 26.05 added validation of add-on zip entries ([release notes](https://github.com/ankitects/anki/releases/tag/26.05)). The build script must produce clean relative paths.

### 3.12 Limitations

| Want | Reality | Decision |
|---|---|---|
| Fully custom deck list layout (cards, icons, drag) | Only by replacing `DeckBrowser` rendering (what Onigiri does) or overlaying our own DOM, which breaks other deck-browser add-ons and Anki's drag-and-drop/collapse JS | CSS transforms the *existing* table into a modern list. No re-render. |
| Restyle SvelteKit pages deeply | Hashed/unstable classes; no pre-render hook | Tokens/accents only, experimental flag |
| Restyle the native title bar / OS chrome | OS-controlled. Anki already handles macOS dark appearance | Out of scope |
| Style every dialog from other add-ons | Global QSS affects them unpredictably | Conservative QSS; per-category toggles |
| Animated transitions in Qt widgets | QSS has no transitions | Animations only in webviews, restrained |
| Change card templates automatically | Would modify user data; syncs to other devices | Never. Optional downloadable templates (Future). |
| Heatmap/stats | Anki's Statistics screen already shows them | Do not duplicate (§5) |

---

## 4. Competitive analysis

| Add-on | Source / license | Status | Approach | Strengths | Weaknesses / conflict risk |
|---|---|---|---|---|---|
| **Onigiri** ([GitHub](https://github.com/thepeacemonk/Onigiri), AnkiWeb [1011095603](https://ankiweb.net/shared/info/1011095603)) | GPL-3.0 (LICENSE file) | Very active; v2.0.1, last commit 2026-10-12; README claims >140k users | Replaces `DeckBrowser._renderPage`, `_render_deck_node`, `Overview._table/_body`; wraps `_show_finished_screen` [verified by reading its source] | Rich dashboard, themes, customization; strong demand signal | Self-described "experimental"/beta; gamification (mini-games, companions, in-add-on purchases) is a different product direction; method replacement conflicts with any deck-browser add-on |
| **Anki Redesign** ([GitHub](https://github.com/Shirajuki/anki-redesign), AnkiWeb [308574457](https://ankiweb.net/shared/info/308574457)) | **No license stated** → no reuse | Last changelog Feb 2023 (v0.1.9); installed copy declares max 25.09.2 [LOCAL] | Hooks + CSS + QSS injection (`webview_will_set_content`, `style_did_init`, `theme_did_change`) | Philosophically closest to our approach; theme files in `user_files` | Unmaintained; known styling gaps after 2.1.56 UI changes |
| Beautify Anki ([1150874988](https://ankiweb.net/shared/info/1150874988)) | Unknown | Old (2020 list); reported issues alongside Review Heatmap ([forum](https://forums.ankiweb.net/t/review-heatmap-and-beautify-anki-not-working-properly/29525)) | Replaces main-screen/overview look | Material look, deck icons | Likely unmaintained; conflicts |
| Button-focused add-ons: The KING of Button Add-ons ([374005964](https://ankiweb.net/shared/info/374005964)), Large and Colorful Buttons ([1829090218](https://ankiweb.net/shared/info/1829090218)), Button Colours ([2494384865](https://ankiweb.net/shared/info/2494384865)), Advanced Review Bottom Bar ([1136455830](https://ankiweb.net/shared/info/1136455830)) | Unknown | Varies | Reviewer bottom bar restyle/replacement | Popular single-purpose fixes | Overlap with our answer-button styling — must coexist (§10.4) |
| Change Interface Font ([1431333984](https://ankiweb.net/shared/info/1431333984)), Custom Background Image and Gear Icon ([1210908941](https://ankiweb.net/shared/info/1210908941)), Dancing Baloney ([378638814](https://ankiweb.net/shared/info/378638814)) | Unknown | Varies | Font / background / custom CSS | Narrow and simple | Overlap with fonts/backgrounds |
| Review Heatmap ([GitHub](https://github.com/glutanimate/review-heatmap), [1771074083](https://ankiweb.net/shared/info/1771074083)) | See repo | Changelog targets 2.1.49+/2.1.50+; status on 26.x unknown | Injects heatmap into deck browser/overview | Well-loved visualization | We should *not* rebuild it; must coexist on the deck browser |

Source for the older list: [Add-ons That Change Anki's Interface (forum wiki)](https://forums.ankiweb.net/t/add-ons-that-change-ankis-interface/1798). Its own warning: "don't install all of these add-ons together… likely that they have conflicts".

AnkiWeb listing pages are JavaScript-rendered and could not be read programmatically. Version support and update dates for the AnkiWeb-only add-ons above are therefore **unknown**, not assumed.

**Opportunity (evidence-based, not a uniqueness claim):**
1. A *maintained*, *hooks-only* restyle for current Anki (25.09–26.09). Redesign occupied this niche but went stale, and Onigiri chose replacement plus gamification.
2. Coexistence as a design goal: Review Heatmap, button add-ons, and Migaku should keep working, verified by a published compatibility table.
3. Accessibility and keyboard rigor (contrast tests, focus rings, reduced motion) that none of the listed projects document.
4. Optional, non-invasive CJK/Japanese reading polish.

**Redundant — do not build:** heatmaps and history charts (Anki's Statistics screen and Review Heatmap), deck search (Anki's **Study Deck** dialog on `/` [SRC `forms/main.ui`]; we surface it instead), custom backgrounds/wallpapers (existing add-ons; low value), gamification.

**Licensing:** No code from Onigiri (GPL-3.0), Anki Redesign (unlicensed = all rights reserved), or others will be copied. Anki itself is AGPL-3.0-or-later. Referencing its CSS variable names is interoperability, not copying its stylesheets.

---

## 5. Feature prioritization

### A. Deck overview (deck browser + overview screens)

| Feature | Tier | Rationale |
|---|---|---|
| Restyle deck list: rows as rounded list items, hierarchy indentation guides, hover/selected/current states, collapse chevrons | **MVP** | CSS over existing table; high visual impact; zero conflict |
| New / Learn / Review counts as tinted pills using `--state-*`; zero counts dimmed | **MVP** | Existing `.new-count`/`.learn-count`/`.review-count` spans [SRC] |
| Bottom-bar actions (Shared/Create/Import) as primary/secondary buttons | **MVP** | Existing buttons in `DeckBrowserBottomBar` |
| Overview: deck title, description card, count summary, prominent "Study Now" | **MVP** | Existing `OverviewContent` |
| Gear (options) icon replaced with a consistent icon via CSS `mask-image` | MVP | Same element; no DOM change |
| "Find deck" affordance that opens Anki's Study Deck dialog (`/`) via `pycmd("refine:studydeck")` → `mw.onStudyDeck()` | **V1** | Reuses existing feature; `mw.onStudyDeck` is internal-ish — wrap in try/except |
| Inline type-to-filter of the deck list | Future | Redundant with Study Deck; extra JS fragility |
| Empty state for a brand-new collection (only "Default", no cards): short guidance + buttons for Create Deck / Get Shared / Import | **V1** | Append via `deck_browser_will_render_content`; detect from `deck_due_tree()` |
| Custom deck icons/emoji, deck backgrounds | Not recommended | Requires per-deck storage, overlaps existing add-ons |
| Replacing the deck list with a new custom renderer | Not recommended | Breaks drag-drop/collapse JS and other add-ons |

### B. Reviewer

| Feature | Tier | Rationale |
|---|---|---|
| Answer buttons: consistent sizing, Again/Hard/Good/Easy semantic tints via `[data-ease]`, interval label hierarchy, focus ring on `#defease`, shortcut hint from existing `title` | **MVP** | Bottom-bar webview, not card content |
| "Show Answer" button, remaining-count display, timer: restyled | **MVP** | Same webview |
| Reviewer canvas: background, `#_mark`/`#_flag` indicators restyled | MVP | Outside `#qa` |
| Type-in-answer input and comparison (`#typeans`, `.typeGood/.typeBad/.typeMissed`) restyled | V1 | Inside card area; low-specificity rules |
| Audio replay buttons (`.replay-button`) restyled; size, focus, hover | V1 | Anki-generated element inside card; zero-specificity rules |
| Images: `max-width:100%`, rounded corners **only** when the card layer is enabled | V1 (opt-in) | Card content; templates may rely on raw layout |
| Card typography layer: comfortable measure (max-width), line-height, CJK fallback stack | V1 (opt-in) | Card content — off by default |
| Japanese ruby/furigana styling (`ruby`, `rt` size, `ruby-position`, hide-until-hover option) | V1 (opt-in) | Works on Anki's `{{furigana:}}` output and hand-written `<ruby>`; zero-specificity |
| `:lang(ja)` font selection; optional "treat this note type as Japanese" mapping | Future | Needs per-notetype config UI |
| Restrained transition between question/answer | Future | Anki already fades `#qa` (`qFade`); stacking animations risks jank; respect reduce-motion |
| Custom audio player UI replacing Anki's `[sound:]` handling | Not recommended | Playback is Python-side (`av_player`); replacing it is invasive |
| Re-ordering or re-labelling answer buttons | Not recommended | Behavior change; conflicts with other add-ons |

### C. Navigation and application chrome

| Feature | Tier | Rationale |
|---|---|---|
| Top toolbar: pill-style nav links, active-state highlight, consistent spacing, sync indicator styling | **MVP** | Webview; CSS only |
| Qt menus: padding, radius, hover, separators, dark-mode consistency | **MVP** | QSS via `style_did_init` |
| Scrollbars (Qt + webviews), focus rings, tooltips | **MVP** | Small, low-risk |
| Browser window: table row height, header, selection colors, sidebar | V1 | QSS; heavier testing needed |
| Common dialogs (Add-ons, Preferences frame, Profiles): spacing, buttons | V1 | QSS; must not break add-on dialogs |
| SvelteKit pages: accent/radius tokens only | V1 (experimental) | Post-load CSS; unstable selectors |
| Icon set for toolbar | Future | Toolbar links are text by default; icons need a licensed icon set (e.g., Lucide, ISC) and per-link mapping that doesn't break other add-ons' links |
| Command palette | Not recommended | Shadows Anki's own shortcuts and Study Deck; large scope |
| Replacing Qt menu bar or main window layout | Not recommended | Unsafe |

### D. Themes and preferences

| Feature | Tier | Rationale |
|---|---|---|
| Light/dark tokens that follow Anki's theme setting live | **MVP** | Core |
| Accent palette (8 curated accents, contrast-validated in both themes) | **MVP** | CSS vars + generated QSS |
| Density: Comfortable / Compact | MVP | Spacing scale variable |
| Settings dialog (Qt), per-surface toggles, reset to defaults | **MVP** | `setConfigAction` |
| Interface font choice (system default / bundled font / any installed family) | V1 | System font is fine for MVP (Anki 25.07+ uses system font [release notes](https://github.com/ankitects/anki/releases/tag/25.07)) |
| Custom hex accent with contrast check | V1 | |
| Additional palettes (e.g., warm neutral, high contrast) | V1 | High-contrast mode serves accessibility |
| User CSS override file in `user_files/` | V1 | Power users; survives upgrades |
| Full theme marketplace / theme editor | Not recommended | Scope |

### E. Learning dashboard

Data provenance:
- **Anki-provided:** due counts (`deck_due_tree`), "Studied N cards in X minutes today" (`col.studied_today()` returns a formatted string), and full history in the Statistics screen.
- **Add-on-computed (read-only, from `revlog`):** today's review count/time as numbers, streak, goal progress.

| Feature | Tier | Rationale / cost |
|---|---|---|
| "Today" strip: reviews done, time spent, cards still due | **V1** | One bounded revlog query + existing due tree; cheap |
| Daily goal (cards or minutes) with a progress bar | V1 | Stored in add-on config per profile; no collection writes |
| Study streak (consecutive days with ≥1 review, respecting the day-rollover hour via `col.sched.day_cutoff`) | V1 | Bounded backward scan of distinct day buckets; cached per day; invalidate on `reviewer_did_answer_card`/`sync_did_finish`/`day_did_change` |
| Per-deck progress (done today / due) on the overview | Future | Requires deck-filtered revlog queries incl. subdecks |
| 26-week activity heatmap (compact, home screen) | **Built in 0.1.0** | Revised 2026-10-24: the user's design ("Anki Revamp") includes it. Read-only revlog query in a background QueryOp, same day boundaries as Anki; each home panel can be turned off. |
| Full historical charts | **Not recommended** | Anki's Statistics already has them (and is now themed by Refine) |
| Separate review-history store | **Not recommended** | Duplicates revlog; sync/consistency risk |

Day boundaries (verified in M0, Q4): `col.sched.day_cutoff` is the epoch-seconds start of the *next* day and follows the rollover preference immediately. "Today" must use Anki's own formula: `revlog.id > (day_cutoff − 86400)·1000 AND type NOT IN (4, 5)`, which excludes Manual and Rescheduled entries. Only then do the counts match `col.studied_today()`.

### F. Compatibility and reliability

| Feature | Tier |
|---|---|
| Per-surface error guards with auto-disable, version/hook gating | **MVP** |
| Global kill switch + Shift-start documentation | **MVP** |
| Compatibility test pass with common add-ons (§10.4) | **MVP** (top 5), V1 (extended) |
| Diagnostics dialog with copyable report | V1 |
| Selector-contract self-check | V1 (CI from M1) |

---

## 6. UI specification and design system

### 6.1 Design principles

1. **Content first.** The card and the deck list are the product; chrome recedes. Neutral surfaces, one accent.
2. **Hierarchy by type and space, not boxes.** Prefer spacing and weight over borders; use borders at 1 px in `--border-subtle`.
3. **Quiet motion.** 120–180 ms opacity/transform only, on hover/press/expand. None when reduce-motion is set.
4. **Native-feeling.** Use the system UI font. No web-app affordances, such as giant hero headers or marketing gradients.
5. **Never block the habit.** No interstitials, no mandatory dashboard, no clicks added to the study path.

### 6.2 Tokens

The add-on defines its own `--rf-*` tokens and **maps them onto Anki's tokens by default**. That way unstyled Anki elements and other add-ons inherit the same palette.

**Color (semantic roles, both themes):**

| Token | Light | Dark | Use |
|---|---|---|---|
| `--rf-bg` | `#F7F7F8` | `#141416` | window canvas |
| `--rf-surface` | `#FFFFFF` | `#1C1C1F` | cards, rows, menus |
| `--rf-surface-hover` | `#F0F0F2` | `#242428` | hover |
| `--rf-surface-sunken` | `#EFEFF1` | `#101012` | inputs, inset |
| `--rf-border` | `#E4E4E7` | `#2C2C31` | subtle dividers |
| `--rf-border-strong` | `#D1D1D6` | `#3A3A40` | controls |
| `--rf-text` | `#18181B` | `#EDEDEF` | primary text |
| `--rf-text-muted` | `#5B5B66` | `#A1A1AA` | secondary text (≥4.5:1 checked) |
| `--rf-accent` | per palette (default indigo `#5B5BD6` / `#8B8DF8`) | | primary actions, focus |
| `--rf-accent-fg` | computed for contrast | | text on accent |
| `--rf-new` / `--rf-learn` / `--rf-review` | derived from Anki `--state-*` hue, tuned for contrast | | count pills |
| `--rf-again` / `--rf-hard` / `--rf-good` / `--rf-easy` | red / amber / green / blue (tints at 12–16% alpha for backgrounds, solid for text/border) | | answer buttons |
| `--rf-focus` | `--rf-accent` at 2 px + 2 px offset | | focus ring |

Hex values are starting points. The automated contrast test (§10.5) is the arbiter, and values change if they fail.

**Type scale** (system UI font; `font-feature-settings: "tnum"` for counts): 12 / 13 / 14 (base UI) / 16 / 20 / 24. Weights 400/500/600. Line height 1.45 for UI, 1.6 for card layer. CJK fallback stack in the card layer: `"Hiragino Sans", "Yu Gothic UI", "Meiryo", "Noto Sans JP", sans-serif` (Windows/macOS/Linux coverage). Fonts are used only if present; none are bundled in MVP.

**Spacing:** 4-pt scale `2, 4, 8, 12, 16, 24, 32, 48`. Compact density multiplies the row padding by 0.75.

**Radii:** 6 (controls), 10 (rows/cards), 14 (panels). These align with Anki's 5/12/15 scale.

**Elevation:** two levels only: `0 1px 2px rgb(0 0 0 / .06)` and `0 4px 16px rgb(0 0 0 / .08)`. In dark mode, borders replace shadows.

**Motion:** `--rf-dur: 140ms; --rf-ease: cubic-bezier(.2,.0,.0,1)`. Disabled under `.reduce-motion` and `@media (prefers-reduced-motion: reduce)`. Anki's `reduce_motion` preference **defaults to on** (`profiles.py:543`, verified in M0), so most users see no transitions. Every state change must read clearly without motion.

### 6.3 Keyboard and interaction rules

- Never rebind or swallow Anki keys. Global: `d a b t Shift+t y s Ctrl+:` [SRC `main.py:1179-1188`]. Menu: `/` Study Deck [SRC `forms/main.ui`]. Reviewer: `e space m r * = - ! @ v Shift+v o i Ctrl+Alt+N Ctrl+Alt+E Ctrl+Backspace Ctrl+Shift+D Ctrl+Alt+i`, answer keys 1–4 and the configurable answer keys [SRC `reviewer.py:_shortcutKeys`]. The add-on defines **no new global shortcuts in MVP**.
- Visible focus for every interactive element in styled webviews (`:focus-visible` ring), plus Tab order equal to DOM order (unchanged).
- Hover is never the only way to reveal information. For example, the furigana hide-until-hover mode also reveals on focus and on answer side.
- Pointer targets ≥ 32 px tall for answer buttons and ≥ 28 px for deck rows (comfortable).

### 6.4 Screen-by-screen

**Top toolbar (webview, `TopToolbar` context).**
Centered nav (Decks · Add · Browse · Stats · Sync) as text pills with 8 px horizontal padding and a 6 px radius. The current screen gets an accent-tinted pill, driven from `state_did_change` by adding a class on the toolbar `<body>`. The sync indicator keeps Anki's states and only gets recoloring. Links added by other add-ons inherit pill styling through generic selectors but are not reordered. Height (verified in M0, Q3): the toolbar webview has a fixed Qt height measured only in `Toolbar.draw()`. CSS delivered via `webview_will_set_content` sizes correctly. CSS injected later is clipped until `mw.toolbar.web.adjustHeightToFit()` runs. Live changes therefore inject the style and then call it, guarded. `Toolbar.redraw()` does not re-render. Auto-hide-in-review mode is still to be tested in M2.

**Deck browser (webview, `DeckBrowser` context).**
```
┌──────────────────────────────────────────────────────────────┐
│  Decks                                       New  Learn  Due │  ← header row (existing <th>)
│ ──────────────────────────────────────────────────────────── │
│ ▸ Japanese                                    20    4    112 │  ← row = surface, radius 10, hover
│     ├ Core 2k                                 10    2     80 │  ← indent guide (left border)
│     └ Kanji                                   10    2     32 │
│ ▸ Medicine                                     ·    ·     45 │  ← zero counts dimmed "·"
│                                                          ⚙   │  ← gear appears on row hover/focus
│  Studied 84 cards in 21 minutes today.                       │  ← existing stats line, muted
└──────────────────────────────────────────────────────────────┘
          [ Get Shared ]  [ + Create Deck ]  [ Import File ]    ← bottom bar; Create = primary
```
- Max content width 880 px, centered; the table stretches to the container.
- The current deck row (`tr.deck.current`) gets an accent left marker. Filtered decks (`a.deck.filtered`) get a muted tint [SRC `deckbrowser.py:242-264`].
- Count cells use tabular numerals and pill backgrounds at low alpha. Zero counts render as `<span class="zero-count">` instead of the per-state class [SRC `deckbrowser.py:279-282`] and are shown at `--rf-text-muted`.
- The drag-to-reparent behavior (jQuery UI from `deckbrowser.js`) must keep working. Rows keep `display: table-row` (no grid conversion). Only padding, background, and border-radius via cell pseudo-styling.
- Empty state (V1): an inline panel above the table with one sentence and three buttons wired to existing commands (`create`, `shared`, `import` pycmds of the bottom bar).
- "Today" strip (V1): a single-line panel above the deck list, e.g. `84 reviews · 21 min · 157 due · Goal 84/150 ▓▓▓▓▓░░ · 12-day streak`. It is collapsible, and its collapse state persists in config.

**Overview (webview, `Overview` context).**
The deck name is a 24 px semibold title. The description renders in a surface card with a capped height and "Show more" (CSS only, `details` not required). The New/Learning/To-Review table becomes three stat tiles (still the same table, styled). "Study Now" is the single primary button, large (40 px), in the accent color. Secondary actions sit in the bottom bar as ghost buttons. The congrats screen is SvelteKit: tokens only (V1).

**Reviewer (webview, `Reviewer` + `ReviewerBottomBar` contexts).**
- Card area: background `--rf-bg`. **No changes inside `#qa` by default.** The optional card layer adds the `rf-card-layer` class to `<body>`, which enables `:where(.rf-card-layer #qa)` rules: max-width 720 px measure, line-height 1.6, image max-width, ruby styling, CJK stack.
- Bottom bar:
```
           ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
           │  Again   │ │   Hard   │ │   Good   │ │   Easy   │
           │   <1m    │ │   6m     │ │   1d     │ │   4d     │
           └──────────┘ └──────────┘ └──────────┘ └──────────┘
   20 + 4 + 112                                           0:14
```
  Equal-width buttons (min 96 px). Ease colors are applied as a 3 px bottom border plus a tinted hover background, not full saturated fills (less visual noise, color-blind safe with labels intact). `#defease` gets the focus ring. Interval labels are muted. The "Show Answer" button is the same shape, in accent. Counts reuse the deck-browser pill tints. If another add-on adds or removes buttons, the layout still works (flex on the existing `td`s).
- Audio (V1): `.replay-button` becomes a 28 px circular icon button with a focus ring. Anki's playback logic is unchanged.

**Qt chrome (QSS).**
- MVP: `QMenuBar`, `QMenu` (padding 6, item radius 6, hover = surface-hover, separators = border), `QToolTip`, `QScrollBar` (thin, rounded thumb), focus outline color on `QLineEdit/QComboBox/QSpinBox`.
- V1: `QTableView` in the Browser (row height via the `Browser` setting stays Anki's; we only style header, gridlines, selection), `QTreeView` sidebar, `QPushButton` default/primary via `:default`, `QTabWidget`, `QGroupBox`.
- QSS is only applied when Anki's *widget style* is "Anki" (`WidgetStyle.ANKI`) [SRC `theme.py:249`]. With "Native" style selected, we honor the user's choice and only add the menu/scrollbar subset **[decision — see Open Questions]**.

**Settings dialog (Qt).**
A single window with sections: *Appearance* (accent swatches, density, font), *Surfaces* (checkbox per surface with one-line descriptions), *Reviewer card layer* (off by default; CJK/ruby sub-options), *Today strip* (V1: goal type/value), and *Advanced* (experimental SvelteKit theming, user CSS file, diagnostics, **Reset to defaults**). Changes apply live, and there is a "Restore" button for undoing the dialog's changes.

---

## 7. Architecture

### 7.1 Components and boundaries

```
__init__.py ──(guarded import)──▶ refine.bootstrap.setup()
                                     │
       ┌─────────────────────────────┼───────────────────────────────┐
       ▼                             ▼                               ▼
 compat/                      config/                         diagnostics/
  version.py  (int_version,    schema.py   (defaults,          log.py (logging →
   gates)                       validation, migration)          user_files/logs)
  hooks.py   (hook presence)   store.py    (get/write,         guard.py (@guarded:
                                per-profile, change events)     catch, count, auto-disable)
                                                                report.py (V1 dialog)
       └───────────────┬───────────────────────────┘
                       ▼
                 theme/
                  tokens.py   palette → token dict (light/dark), contrast math
                  css.py      tokens → :root CSS custom props string
                  qss.py      tokens → QSS string (marked block)
                       │
                       ▼
                 surfaces/   (each implements Surface protocol)
                  base.py          Surface: id, requires_hooks, min_version,
                                   web_contexts, install(), uninstall(), on_config()
                  toolbar.py       TopToolbar/BottomToolbar CSS + active-state class
                  deck_browser.py  CSS; V1: empty state, Today strip mount point
                  overview.py      CSS
                  reviewer.py      bottom-bar CSS, reviewer canvas CSS, opt-in card layer
                  qt_chrome.py     style_did_init filter; marked-block live re-apply
                  ts_pages.py      (V1, experimental) webview_did_inject_style_into_page
                       │
                       ▼
                 web/        static assets served via setWebExports
                  css/base.css, deck-browser.css, overview.css, reviewer.css,
                      reviewer-bottom.css, toolbar.css, card-layer.css, ts-pages.css
                  js/refine.js   (root class, active-state, pycmd bridge, selector probe)
                  icons/*.svg
                       │
 dashboard/ (V1)        ▼
  queries.py   pure functions: (col, window) → stats   [run in QueryOp]
  model.py     TodayStats dataclass, streak calc (pure, unit-tested)
  cache.py     per-profile, per-day cache + invalidation hooks
  view.py      HTML fragment for deck_browser_will_render_content

 ui/
  settings_dialog.py   Qt dialog (aqt.qt imports only)
  menu.py              Tools ▸ Refine submenu
```

Module rules:
- `theme/`, `config/schema.py`, and `dashboard/model.py` are **pure Python** with no `aqt` imports, so they can be unit-tested without Anki.
- Only `surfaces/*`, `ui/*`, and `bootstrap.py` import `aqt`. Only `dashboard/queries.py` touches `col`, and only for reads.
- No surface imports another surface. Shared behavior lives in `surfaces/base.py`.

### 7.2 Data flow

**Webview styling (legacy screens):**
```
Anki screen → AnkiWebView.stdHtml → gui_hooks.webview_will_set_content(wc, ctx)
   → registry.dispatch(ctx)                      # isinstance → matching surfaces
      → surface.contribute(wc):
           wc.css.append("/_addons/<pkg>/web/css/<surface>.css")
           wc.head += <style id="rf-tokens">{css.render(tokens)}</style>
           wc.js.append("/_addons/<pkg>/web/js/refine.js")
   → Anki assembles HTML; Anki's own night-mode classes drive light/dark
```

**Theme change:** `theme_did_change` → Anki updates webview classes itself (no work for us). Anki re-runs `_apply_style` → our `style_did_init` filter returns `buf + qss.render(tokens_for(night_mode))`.

**Config change:** `config.store` emits `changed(keys)` → affected surfaces call `on_config()`. Webview surfaces replace their `<style id="rf-tokens">` in each open webview via `web.eval()`. This applies instantly, has no side effects, and needs no re-render (verified in M0, Q5). Future renders pick the change up through `webview_will_set_content`. Never `mw.reset()`: when focused it re-shows the question and drops a revealed answer. `mw.moveToState("review")` re-renders but flips to the question side. `qt_chrome` replaces the marked QSS block in `mw.app.styleSheet()` and calls `setStyleSheet` (public Qt API, no Anki internals).

**Dashboard (V1):** `deck_browser_will_render_content` → `cache.get_today()`. On a hit, the fragment is appended to `content.stats`. On a miss, it returns a placeholder and schedules `QueryOp(queries.today)`; on success it updates the DOM via `web.eval` or a single refresh, guarded against loops.

### 7.3 Initialization lifecycle

1. **Import** (`__init__.py`): `try: from .bootstrap import setup; setup() except Exception: log + bail`. No Anki state is touched.
2. **`setup()`**: read the version, load and migrate config, `setWebExports`, register `main_window_did_init`.
3. **`main_window_did_init`**: build the surface registry and filter by version, hooks, and config. Each enabled surface's `install()` appends its hooks. Register `setConfigAction` and the Tools menu. If Qt chrome is enabled, insert the marked QSS block into `mw.app.styleSheet()` once. This is required: in `AnkiQt.__init__`, `setupUI()` → `setupStyle()` → `apply_style()` runs **before** `setupAddons()` [SRC `main.py:198-200, 233`]. Our `style_did_init` filter therefore misses the first application, and `apply_style()` early-returns when neither theme nor widget style changed [SRC `theme.py:224-232`]. From then on, the filter handles every theme change.
4. **`profile_did_open`**: load per-profile config; the dashboard cache is reset.
5. **Runtime**: hooks dispatch through `@guarded` (try/except → log → error counter; after 3 errors in a session, `surface.uninstall()` and show a one-time non-modal tooltip "Refine disabled <surface> due to an error — see Diagnostics").
6. **`profile_will_close`**: drop caches. Nothing to persist into the collection.
7. **Disable at runtime** (toggle or kill switch): `uninstall()` removes hooks (`hook.remove(fn)`), removes the QSS block, and refreshes the current screen.

### 7.4 Error-handling contract

- Every hook callback is wrapped. Filters return the input unchanged on error.
- Asset loading: if a web-export file is missing, the page simply lacks our CSS, which is a graceful degradation.
- Never `assert` for runtime checks (stripped in release builds [DOC debugging]).
- Never write to stderr except through Anki's error path for genuinely user-actionable failures.

---

## 8. Proposed project structure

```
AnkiAddOn/                         ← repository root (this directory)
├── PLAN.md
├── README.md                      install, config, troubleshooting, rollback
├── LICENSE                        AGPL-3.0-or-later
├── CHANGELOG.md
├── pyproject.toml                 dev tooling only (ruff, mypy, pytest config)
├── requirements-dev.txt           aqt[qt6]==<pinned>, pytest, mypy, ruff
├── scripts/
│   ├── build.py                   → dist/refine-<ver>.ankiaddon (clean zip, no __pycache__)   (M5)
│   ├── devenv.py                  venvs, isolated profiles, linking, launch+DevTools, snapshots, report (M0 ✅)
│   └── check_contrast.py          CLI wrapper around theme.tokens contrast validation          (M1)
├── devtools/
│   ├── m0_probe/                  dev-only probe add-on (never shipped)                        (M0 ✅)
│   └── htmlinventory.py           stdlib HTML/selector helpers for report + contract tests     (M0 ✅)
├── docs/                          M0-REPORT.md (analysis), M0-RESULTS.md (generated)
├── src/
│   └── refine/                    ← the add-on (zipped contents)
│       ├── __init__.py            guarded bootstrap only
│       ├── manifest.json          package, name, conflicts=[], mod
│       ├── config.json            defaults (schema_version, surfaces, appearance…)
│       ├── config.md              user-facing config docs
│       ├── bootstrap.py
│       ├── compat/{__init__,version,hooks}.py
│       ├── config/{__init__,schema,store}.py
│       ├── diagnostics/{__init__,log,guard,report}.py
│       ├── theme/{__init__,tokens,palettes,css,qss,contrast}.py
│       ├── surfaces/{__init__,base,registry,toolbar,deck_browser,overview,reviewer,qt_chrome,ts_pages}.py
│       ├── dashboard/{__init__,queries,model,cache,view}.py      (V1)
│       ├── ui/{__init__,settings_dialog,menu}.py
│       ├── web/
│       │   ├── css/{base,toolbar,deck-browser,overview,reviewer,reviewer-bottom,card-layer,ts-pages}.css
│       │   ├── js/refine.js
│       │   └── icons/*.svg        (licensed icon subset; attribution in LICENSES/)
│       ├── LICENSES/              third-party notices (icons/fonts if any)
│       └── user_files/README.txt  keeps folder on upgrade; user CSS + logs live here
└── tests/
    ├── unit/                      pure-python: tokens, contrast, config migration, streak math
    ├── contract/                  hook-name and selector-contract tests vs pinned aqt versions
    │   ├── test_hooks_exist.py
    │   └── fixtures/<anki-ver>/{deckbrowser,overview,reviewer,bottom}.html
    ├── integration/               CDP-driven checks against a running dev Anki (opt-in)
    └── manual/CHECKLIST.md        release checklist (§10.7)
```

`src/refine/` is zipped, and `tests/` and `scripts/` never ship. The folder name `refine` is only for local/GitHub installs. AnkiWeb installs land under the numeric ID, so code must never hardcode its folder name (use `__name__` / `addonFromModule`).

---

## 9. Implementation roadmap

| # | Milestone | Depends on | Deliverables | Done when |
|---|---|---|---|---|
| **M0** ✅ done 2026-10-24 ([report](docs/M0-REPORT.md)) | Environment & verification spike | — | Repo scaffold, dev-link script, isolated test profile (`Anki.exe -b <dir>`), remote-debugging on; **resolve every [UNVERIFIED] item** in this plan (Chromium version, 25.09 class names, toolbar height behavior, `day_cutoff`, reviewer refresh API); capture HTML fixtures of each legacy screen from 25.09.x and 26.09.3 | Findings appended to PLAN.md §3; fixtures committed; empty add-on loads and unloads cleanly on both versions |
| **M1** ✅ | Core foundation | M0 | `compat`, `config` (schema+migration), `diagnostics` (log, guard), `theme` (tokens, contrast, css, qss), surface registry, bootstrap, kill switch | Unit tests green; contrast test passes for all palettes; a deliberately failing dummy surface auto-disables without an Anki error dialog |
| **M2** ✅ | Deck browser + overview + toolbar | M1 | CSS surfaces with live theme switching | Visual checklist passes in light/dark at 100/150/200% scaling; drag-reparent, collapse, gear menu, and Shift-click still work; selector contract passes on both fixtures |
| **M3** ✅ | Reviewer chrome | M1 | Bottom bar + answer buttons + reviewer canvas | All reviewer shortcuts verified (§10.3); button styling correct with 2, 3, 4 buttons (via another add-on altering the count); Migaku installed: no regressions vs baseline |
| **M4** ✅ | Qt chrome (MVP subset) + settings dialog | M1 | QSS menus/scrollbars/tooltips/focus; settings dialog; reset; live re-apply | Theme toggle Light↔Dark↔System updates QSS live; reset restores `config.json` defaults; "Native" widget style respected |
| **M5** ✅ (v0.1.0 tagged locally; AnkiWeb upload pending) | **MVP release (0.1.0)** | M2–M4 | Build script, README (install/troubleshooting/rollback), compatibility table, AnkiWeb listing | Acceptance criteria §14 all checked; tested on 25.09.x and 26.09.3 on Windows + at least one of macOS/Linux |
| **M6** ◐ (Japanese layer done; audio/type-answer not started) | V1: card layer, Japanese typography, audio buttons, type-answer | M5 | `card-layer.css`, settings sub-section | Tested on ≥10 diverse shared decks incl. Japanese (furigana via `{{furigana:}}`, hand `<ruby>`), image occlusion, cloze, MathJax; default-off verified as pixel-identical to M5 |
| **M7** ◐ (Today/Activity/streak/forecast + empty state done; daily goal not started) | V1: Today strip + goal + streak, empty state, Study Deck affordance | M5, M0 `day_cutoff` finding | `dashboard/*` | Query < 50 ms on 500k-revlog collection (off main thread); values match Anki's "Studied N cards" line and Statistics for the same day; no collection writes (verified by checking `col.mod` unchanged) |
| **M8** ◐ (browser QSS, diagnostics, Stats/Options/congrats done; custom hex + user CSS not started) | V1: Browser/dialog QSS, accent custom hex, user CSS, diagnostics dialog, experimental SvelteKit tokens | M5 | | Extended add-on compatibility pass (§10.4); diagnostics report useful in a dry-run bug report |
| **M9** | **V1 release (1.0.0)** | M6–M8 | | Full regression + perf suite; 2-week beta via GitHub pre-release with feedback incorporated |

---

## 10. Testing strategy

### 10.1 Unit tests (pytest, no Anki runtime)
- Token generation for every palette × theme, CSS/QSS rendering snapshots.
- Contrast (WCAG relative luminance) for all text/background pairs (§10.5).
- Config: defaults, unknown-key tolerance, migrations from every prior `schema_version`, invalid values clamped.
- Streak/goal math with synthetic revlog rows, including the day-rollover hour, timezone, gaps, and today-with-no-reviews.

### 10.2 API-compatibility / contract tests
- `test_hooks_exist.py`: for each pinned `aqt` version, installed via `py scripts/devenv.py venvs` into separate venvs, assert every hook in each surface's `requires_hooks` exists in `aqt.gui_hooks` and that `WebContent` has `css/js/head/body`. Every release from 2.1.24 to 26.9.3 is on PyPI (verified in M0). Install with **`aqt[qt]`**: the editor-setup doc's `aqt[qt6]` names no extra, and pip then installs the newest PyQt6 instead of the release's pin.
- Selector contract: implemented in M0 as `tests/contract/test_selectors.py` (stdlib only), run against captured fixtures for every target.
- Selector contract: run `refine.js`'s probe logic (pure function over a DOM) against captured HTML fixtures per version, using a headless browser in CI. A missing selector fails the build for that version.

### 10.3 Reviewer behavior and keyboard shortcuts (manual + CDP-assisted)
For each of: basic, reversed, cloze, type-in-answer, image occlusion, audio auto-play, and MathJax cards:
- Space/Enter shows the answer; 1–4 answer; each `_shortcutKeys` entry triggers its action (edit, mark, replay, flags, bury, suspend, undo, card info, options). Verify the visible result in Anki, not just the absence of errors.
- The default-ease focus ring follows `#defease`.
- With the card layer **off**, take a screenshot of `#qa` with and without the add-on: they must be pixel-identical (same window size). This is the strongest guarantee that templates are untouched.
- Integration harness: drive `Anki.exe -b <testbase>` with `QTWEBENGINE_REMOTE_DEBUGGING`, attach via Chrome DevTools Protocol (e.g., Playwright `connect_over_cdp`) for DOM assertions and screenshots. Keystrokes go to the Qt window, which needs OS-level input, so key tests stay **manual** with a checklist unless a reliable automation path is found in M0.

### 10.4 Add-on compatibility
Test matrix (enabled together with Refine): Migaku (installed), AnkiConnect (installed), Review Heatmap, Advanced Review Bottom Bar, The KING of Button Add-ons, Image Occlusion (built-in now), AJT Japanese / Japanese Support, Onigiri (expected to conflict on the deck browser; document the outcome and recommend disabling Refine's deck-browser surface when Onigiri is active, auto-detected via `addonManager.allAddons()` + enabled state). For each: open every screen, run 20 reviews, toggle the theme, and record the result in `COMPATIBILITY.md`.

### 10.5 Theme switching & accessibility
- Light → Dark → Follow System while on each screen; no flash, no stale colors (webviews + QSS).
- Automated contrast: every `(fg, bg)` token pair ≥ 4.5:1 (text) / 3:1 (UI borders, focus ring) in both themes, for every palette.
- Keyboard-only walk-through: Tab through deck browser, overview, and reviewer bottom bar; every focus is visible.
- Screen reader: NVDA (Windows) / VoiceOver (macOS) smoke test that deck names, counts, and buttons are still announced. We preserve the semantic table and buttons, so we expect parity with stock Anki **[UNVERIFIED baseline: stock Anki's own a11y level is unknown — measure stock first, then ensure no regression]**.
- Reduce motion: with Anki's Preferences ▸ Reduce motion on, no transitions are present (computed style check via CDP).

### 10.6 Performance
- Startup: compare Anki start with and without Refine (`time.perf_counter` around `setup()` and `main_window_did_init` handlers, logged in debug mode). Budget: 50 ms.
- Render: time from `deck_browser_will_render_content` to `deck_browser_did_render` with/without Refine on a generated 3,000-deck / 50k-card collection. Budget: +5 ms. CSS selector complexity is kept flat (no `:has` on large lists).
- Dashboard: query timing on a synthetic 500k-revlog collection; must run in `QueryOp`, with the UI responsive during the query.
- Memory: no growth across 500 reviews (check that `web_content` appends don't accumulate; each render is fresh).

### 10.7 Release regression checklist (manual, every release)
Fresh install, upgrade from the previous version (settings preserved), disable/enable, uninstall (no residue outside the add-on folder), Shift-start safe mode, each Anki version in the matrix, Windows + macOS (+ Linux when available), and 100/150/200% scaling.

---

## 11. Compatibility matrix

| Anki | Python / Qt | Support level | Notes / uncertainties |
|---|---|---|---|
| < 25.07 | Qt5 builds possible | **Not supported** (`min_point_version` 250900) | Qt5 removed upstream in 25.07 |
| 25.07 | 3.13 / Qt 6.x | Not supported (below floor) | Superseded by 25.09; could be lowered later if demand exists |
| **25.09.x** | 3.13 bundled / Qt 6.9.1, QtWebEngine 6.8.2 (Chromium 122), per `aqt[qt]==25.9.5` pins | **Supported, tested** | Many users stuck here because auto-update to 26.05+ is unsupported. Optional older-Qt variants (`qt66`–`qt68`) are untested |
| 26.05 | 3.13 (min 3.10) / Qt 6.11 | Supported, tested | New installer |
| 26.08 | 3.13 / Qt 6.11 | Supported, smoke-tested | Experimental Svelte editor (we don't touch the editor) |
| **26.09.x** (26.09.3) | 3.13 / Qt 6.11.2, PyQt6 6.11.0 [LOCAL] | **Primary target, fully tested** | |
| Future (26.10+) | — | Best effort | Graceful degradation via hook/selector checks; positive `max_point_version` = last tested |

| Platform | Level |
|---|---|
| Windows 10/11 x64 | Primary (dev machine) |
| Windows ARM64 | Best effort (official builds exist since 26.05) |
| macOS 13+ | Tested before each release (need access to a Mac — Open Question) |
| Linux (glibc 2.35+) | Smoke-tested (VM) |

Resolved in M0 ([report](docs/M0-REPORT.md)): Chromium 122 (25.09) and 140 (26.09). Legacy-screen class names are identical in 25.09.5 and 26.09.3. `style_did_init` does **not** fire for add-ons at startup but does on every theme change (§7.3). Remaining uncertainty: macOS/Linux behaviour.

---

## 12. Risks and mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Anki rewrites the deck browser/reviewer (stated intent since 2021) | Medium over 1–2 years | High (surface CSS obsolete) | CSS-only surfaces are cheap to redo; selector contract detects it; surface auto-disables to stock look rather than breaking |
| R2 | DOM/class names change in a point release | Medium | Medium | Selector-contract tests per version in CI; beta-channel testing for each Anki beta |
| R3 | CSS leaks into card content or other add-ons' webviews | Medium | High (user-visible breakage of decks) | Per-context injection; `html.refine` guard; `@layer`; card layer off by default; pixel-identical `#qa` test |
| R4 | Global QSS breaks third-party dialogs | Medium | Medium | Minimal MVP subset; type-selector QSS only for menus/scrollbars/tooltips; per-category toggles; honor "Native" style |
| R5 | Conflicts with method-replacing add-ons (Onigiri, Migaku) | High for Onigiri's deck browser; low for reviewer bottom bar | Medium | We never replace methods, so worst case is visual mismatch; detect Onigiri and default our deck-browser surface off; compatibility table |
| R6 | Another add-on also appends reviewer-bottom CSS with higher specificity | High | Low | Accept (cascade layers let theirs win); document |
| R7 | Exceptions in hooks show Anki error dialogs | Low after guards | High (trust) | `@guarded` wrapper, auto-disable, logging, never stderr |
| R8 | Performance regressions in large collections | Low (CSS) / Medium (dashboard) | Medium | No Python work in render path beyond string append; dashboard in `QueryOp`, cached per day, bounded queries |
| R9 | Contrast/accessibility regressions from custom accents | Medium | Medium | Automated contrast gate; custom hex rejected if it fails |
| R10 | AnkiWeb packaging rejection | Low | Low | Build script with zip validation (no top folder, no `__pycache__`, relative paths) |
| R11 | Japanese typography rules mis-render non-Japanese CJK (Chinese/Korean) | Medium | Low | Opt-in; `:lang()`-scoped where templates set `lang`; generic CJK stack default |
| R12 | Being perceived as "just another theme" | Medium | Product | Lead with reliability and compatibility; publish compat table and changelog discipline |
| R13 | Upstream add-on system revamp (announced June 2026) changes packaging/config | Unknown | Medium | Keep packaging script isolated; follow forum/dev docs |

---

## 13. Distribution strategy

**Development install.** `py scripts/devenv.py run <target>` creates a directory junction (Windows) or symlink (macOS/Linux) from `src/refine` into `addons21/refine` of an **isolated** base folder `.anki-dev/<target>/`, pre-seeds the profile (to skip the first-run language modal), and launches with `-b` and a per-target single-instance key, so the real collection is never touched (`-b/--base` and `-p/--profile` exist [SRC `aqt/__init__.py:490-491`]). See [README](README.md). Remote debugging comes from `QTWEBENGINE_REMOTE_DEBUGGING=8080`. Disabling the "startup add-on update check" (26.05+ preference) avoids AnkiWeb overwriting the dev copy.

**Packaging.** `scripts/build.py` zips `src/refine/*` (excluding `__pycache__`, `*.pyc`, `user_files/*` except `README.txt`, dev files) into `dist/refine-<semver>.ankiaddon`. It validates paths, includes `manifest.json`, and stamps `mod`.

**Versioning.** SemVer in `manifest.json` and CHANGELOG (`0.x` = MVP/beta, `1.0.0` = V1). Config `schema_version` is integer-incremented, with migrations. `min_point_version: 250900`. `max_point_version` (positive) = highest Anki tested.

**Release channels.**
1. GitHub pre-release `.ankiaddon` for beta testers (install via Tools ▸ Add-ons ▸ Install from file).
2. AnkiWeb listing for stable releases, with a description stating the compatibility table, what it does *not* change (card templates, scheduling, data), and the rollback steps.

**Rollback (documented in README).**
1. Immediate: Refine settings ▸ disable all surfaces, or Tools ▸ Add-ons ▸ uncheck Refine (no restart needed for visuals after refresh; restart recommended).
2. If Anki won't start normally: hold **Shift** while launching (safe mode, add-ons off) and disable Refine.
3. Previous version: install the prior `.ankiaddon` from GitHub Releases (we keep all releases). AnkiWeb itself serves only the latest version **[UNVERIFIED — check AnkiWeb branch support during M5]**.
4. Full removal: delete the add-on in Tools ▸ Add-ons. Refine stores nothing in the collection, so there is nothing to clean up in decks or sync.

---

## 14. Acceptance criteria — MVP (0.1.0)

1. Installs from a `.ankiaddon` on Anki 25.09.x and 26.09.3 (Windows, plus macOS or Linux) with no errors in `anki-console` output.
2. With the add-on enabled, deck browser, overview, reviewer bottom bar, top toolbar, and Qt menus/scrollbars render per §6 in Light, Dark, and Follow-System, and switching themes updates all of them without restart.
3. `#qa` card area screenshots are pixel-identical with the add-on enabled vs disabled (card layer off) for the 7 card types in §10.3.
4. Every global and reviewer shortcut listed in §6.3 performs the same action as in stock Anki (manual checklist signed off).
5. Deck drag-to-reparent, collapse/expand, gear menu, Shift-click select, and options all work in the restyled deck browser.
6. `col.mod` and `col.db` are unchanged after a session of browsing + 50 reviews beyond what stock Anki itself writes (compare with/without add-on), and sync completes normally.
7. All token pairs pass WCAG AA contrast in both themes for all shipped accents (automated test).
8. Disabling any single surface restores stock appearance for that surface after refresh. The global kill switch restores all of them. "Reset to defaults" restores `config.json` values.
9. An injected exception in any surface (test build) results in that surface auto-disabling and a logged entry, with **no** Anki error dialog and no effect on reviewing.
10. Startup overhead ≤ 50 ms and deck-browser render overhead ≤ 5 ms on the reference collection.
11. With Migaku and AnkiConnect enabled, no new errors, and reviewing works (answer buttons, Migaku's reviewer features).
12. The `.ankiaddon` contains no `__pycache__`, no top-level folder, and is accepted by AnkiWeb upload.
13. README covers install, configuration, troubleshooting (bisecting, safe mode, remote debugging), rollback, and the compatibility table.

---

## 15. Open questions

1. **Product scope vs Onigiri.** Is a "polished, reliable, conservative" restyle the product you want, or do you want dashboard-centric deck browser layouts too? The latter would require replacing Anki's rendering, which this plan advises against.
2. **Native widget style.** If the user picked Anki's "Native" widget style, should Refine still restyle Qt widgets (overriding their choice) or only webviews? The plan defaults to webviews plus the menu/scrollbar subset.
3. **Version floor.** Is supporting 25.09.x worth the extra test pass? This plan says yes because of the broken auto-update path. Dropping it would simplify M0–M5.
4. **Test hardware.** Do you have access to macOS (and Linux) for release testing? If not, macOS support should be labeled best-effort.
5. **Name and branding.** "Refine" is a placeholder. A final name should be checked against AnkiWeb listings for collisions.
6. **License.** AGPL-3.0-or-later is recommended (matches Anki, AnkiWeb-compatible). Confirm.
7. **Bundled fonts.** Should we bundle an interface font (e.g., Inter, OFL-licensed) and/or Noto Sans JP subset for the card layer? It adds size and licensing notices. The plan defaults to system fonts only.
8. **Japanese priority.** Should the Japanese card layer move into MVP? It is opt-in either way. The plan keeps it in V1 to protect the MVP timeline.
9. **Dashboard goal unit.** Daily goal in cards, minutes, or both?
10. **Technical items:** Chromium versions, 25.09 class names, toolbar height, `day_cutoff`, reviewer refresh, and PyPI availability are all **resolved in M0** ([report](docs/M0-REPORT.md)). Still open: AnkiWeb rollback/branch behaviour (M5), toolbar auto-hide in review (M2), macOS/Linux runs.

---

### Source index

- Official add-on docs: [intro](https://docs.ankiweb.net/addons/intro) · [add-on folders](https://docs.ankiweb.net/addons/addon-folders) · [config](https://docs.ankiweb.net/addons/addon-config) · [hooks & filters](https://docs.ankiweb.net/addons/hooks-and-filters) · [monkey patching](https://docs.ankiweb.net/addons/monkey-patching) · [sharing](https://docs.ankiweb.net/addons/sharing) · [the anki module](https://docs.ankiweb.net/addons/the-anki-module) · [background ops](https://docs.ankiweb.net/addons/background-ops) · [Qt](https://docs.ankiweb.net/addons/qt) · [reviewer JavaScript](https://docs.ankiweb.net/addons/reviewer-javascript) · [debugging](https://docs.ankiweb.net/addons/debugging) · [editor setup](https://docs.ankiweb.net/addons/editor-setup) (the old `addon-docs.ankiweb.net` URLs redirect here)
- Anki source @ 26.09.3: [webview.py](https://github.com/ankitects/anki/blob/26.09.3/qt/aqt/webview.py) · [theme.py](https://github.com/ankitects/anki/blob/26.09.3/qt/aqt/theme.py) · [deckbrowser.py](https://github.com/ankitects/anki/blob/26.09.3/qt/aqt/deckbrowser.py) · [overview.py](https://github.com/ankitects/anki/blob/26.09.3/qt/aqt/overview.py) · [reviewer.py](https://github.com/ankitects/anki/blob/26.09.3/qt/aqt/reviewer.py) · [toolbar.py](https://github.com/ankitects/anki/blob/26.09.3/qt/aqt/toolbar.py) · [addons.py](https://github.com/ankitects/anki/blob/26.09.3/qt/aqt/addons.py) · [genhooks_gui.py](https://github.com/ankitects/anki/blob/26.09.3/qt/tools/genhooks_gui.py) · [_vars.scss](https://github.com/ankitects/anki/blob/26.09.3/ts/lib/sass/_vars.scss)
- Release notes: [25.07](https://github.com/ankitects/anki/releases/tag/25.07) · [25.09](https://github.com/ankitects/anki/releases/tag/25.09) · [26.05](https://github.com/ankitects/anki/releases/tag/26.05) · [26.08](https://github.com/ankitects/anki/releases/tag/26.08) · [26.09](https://github.com/ankitects/anki/releases/tag/26.09) · [26.09.3](https://github.com/ankitects/anki/releases/tag/26.09.3)
- Forum: [Add-ons That Change Anki's Interface](https://forums.ankiweb.net/t/add-ons-that-change-ankis-interface/1798) · [Implementing Redesign into base code](https://forums.ankiweb.net/t/implementing-redesign-add-on-into-ankis-base-code/12831) · [Updates from the Anki Team — June 2026](https://forums.ankiweb.net/t/updates-from-the-anki-team-june-2026/70120) · [Review Heatmap and Beautify Anki not working](https://forums.ankiweb.net/t/review-heatmap-and-beautify-anki-not-working-properly/29525)
- Competitors: [Onigiri](https://github.com/thepeacemonk/Onigiri) · [Anki Redesign](https://github.com/Shirajuki/anki-redesign) · [Review Heatmap](https://github.com/glutanimate/review-heatmap)

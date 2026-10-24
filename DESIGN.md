# Design

Visual system of Refine, as implemented (tokens: `src/refine/theme/`; styles: `src/refine/web/css/`). Source of the direction: the user's "Anki Revamp" design (Claude Design project "Anki UI revamp discussion").

## Visual theme

Calm, warm, quiet. Near-black warm neutrals in dark mode and warm off-white in light mode, one accent (jade by default), inverted primary buttons (text colour as background). Content, not chrome, carries emphasis: the serif "cards waiting" headline and the card itself are the loudest elements.

## Color

All values are tokens (`--rf-*`), generated per theme and accent and checked by `tests/unit/test_tokens.py` against WCAG AA rules.

| Role | Light | Dark | Use |
|---|---|---|---|
| bg | #F6F5F2 | #1A1918 | window/page background |
| surface | #FFFFFF | #222120 | panels, table, inputs |
| surface-hover / active | #F1F0EC / #E9E7E2 | #2A2927 / #31302D | hover, pressed, selected nav |
| surface-sunken | #EFEDE8 | #151413 | sidebar |
| border / border-strong | rgba(0,0,0,.07) / .14 | rgba(255,255,255,.06) / .12 | dividers / control outlines |
| text / muted / faint | #1C1B19 / #6B6862 / #8C8981 | #ECEBE7 / #A3A098 / #6E6B64 | primary / secondary / tertiary text |
| accent (jade) | #1E8466 | #5FCFA6 | selection marker, focus, progress, heatmap |
| primary-bg / fg | #1C1B19 / #FFFFFF | #ECEBE7 / #161514 | the one primary action per screen |
| new / learn / review | #2F6BD8 / #C24A33 / #1E8654 | #7AA9F5 / #F08A7A / #6FD3A0 | Anki's card-state counts |
| again / hard / good / easy | learn / #A86A12 / review / new | same hues, dark variants | answer buttons |

Eight accents (jade, blue, indigo, violet, rose, amber, teal, graphite) swap only the accent family. State colours always appear with a text label, never as the only signal.

## Typography

- UI: Hanken Grotesk 400/500/600 (bundled). Base 14px; scale 12 / 13 / 14 / 16 / 20 / 24 / 30 / 46.
- Display: Newsreader 400 for large numbers and headlines ("409 cards waiting", stat numbers).
- Numerals: JetBrains Mono 400/500 for counts, intervals and key hints.
- Japanese card text (opt-in layer only): system Japanese sans (Hiragino / Yu Gothic / Meiryo / Noto Sans JP).

## Layout

- App shell on Home, Overview and Stats: 224px sidebar (icon rail ≤ 960px) + 60px header + content (max 1180px). Home is a two-column grid (main + 300px side panels), collapsing to one column.
- Spacing scale 4 / 8 / 12 / 16 / 24 / 32 (×0.75 in compact density). Radii 7 (controls) / 10 (buttons, rows) / 14 (panels).
- Panels: surface + 1px border, no shadows in dark mode.

## Components

- **Deck table**: Anki's own table restyled; uppercase muted column headers, mono counts (zero counts dimmed), row hover tint, selection = accent-soft background + 3px inset marker, chevron expand/collapse, per-row Study + info + ⋯.
- **Headline (hero)**: scope line (All decks / deck name · date), serif count, coloured new/learning/due, pace estimate, one primary action.
- **Side panels**: Today (progress or goal), Activity (26-week heatmap, accent ramp via color-mix), Next 7 days (bars, sqrt scale).
- **Sidebar nav items**: icon + label + mono key hint; active = surface-active + accent icon.
- **Answer bar**: transparent on Anki's canvas; Show Answer inverted primary; answer buttons tinted by ease.
- **Settings dialog**: Qt, styled from the same tokens; sections with small labels, live-applying controls.

## Motion

Setting "Motion" (default Smooth): 180ms rise-and-fade on page content when a screen changes (sidebar stays still), 120–140ms colour transitions on hover, panel fade on update. Easing cubic-bezier(.2,0,0,1). The OS reduced-motion preference disables all of it.

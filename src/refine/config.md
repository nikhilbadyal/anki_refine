**Refine** settings

The friendlier way to change these is **Tools ▸ Refine ▸ Settings…**. Edit this JSON only if you prefer to. Invalid values are ignored and replaced by the default.

- `enabled` (true/false): master switch. When false, Anki looks exactly as it does without Refine.
- `accent`: highlight colour. One of `jade` (default), `blue`, `indigo`, `violet`, `rose`, `amber`, `teal`, `graphite`.
- `density`: `comfortable` (default) or `compact`.
- `surfaces`: turn individual screens on or off (all default to true):
  - `toolbar`: the top toolbar (Decks, Add, Browse, Stats, Sync).
  - `deck_browser`: the deck list / home screen.
  - `overview`: the screen shown after you click a deck.
  - `reviewer`: the review screen and its answer bar.
  - `qt_chrome`: menus, scrollbars and other native widgets.
- `reviewer.ease_colors` (true/false, default true): colour the Again / Hard / Good / Easy buttons.
- `home`: panels on the home screen (all default to true):
  - `hero`: the "cards waiting" headline with the Study button.
  - `today`: cards studied and time spent today.
  - `activity`: 26-week activity heatmap with your streak.
  - `forecast`: cards due over the next 7 days.
- `schema_version`: internal; do not edit.

If a screen misbehaves, set its entry under `surfaces` to false. Refine also does this by itself if a screen raises an error.

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
  - `pages`: Statistics, Deck Options and the "finished this deck" screen use Refine's colours and fonts.
  - `sidebar`: left sidebar and header on Home, Overview and Stats, with Statistics shown inside the main window. Off brings back the classic top toolbar and the Stats window.
- `reviewer.ease_colors` (true/false, default true): colour the Again / Hard / Good / Easy buttons.
- `home`: panels on the home screen (all default to true):
  - `hero`: the "cards waiting" headline with the Study button.
  - `today`: cards studied and time spent today.
  - `activity`: 26-week activity heatmap with your streak.
  - `forecast`: cards due over the next 7 days.
- `daily_goal` (number, default 0): cards per day shown as progress in the Today panel. 0 means no goal.
- `cards`: optional card-content polish, both off by default:
  - `japanese`: Japanese font for text your note type marks as Japanese (`lang="ja"`) and tidier furigana. Your note type's styling still wins.
  - `furigana_hover`: hide furigana until you hover it or reveal the answer (needs `japanese`).
- `schema_version`: internal; do not edit.

If a screen misbehaves, set its entry under `surfaces` to false. Refine also does this by itself if a screen raises an error.

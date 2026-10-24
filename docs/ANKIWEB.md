# AnkiWeb listing

Add-on code **1616260025**: <https://ankiweb.net/shared/info/1616260025>

Everything needed for the upload form at <https://ankiweb.net/shared/upload> (log in first). Re-use it for later updates: open the add-on from <https://ankiweb.net/shared/mine>, choose Update, and upload the new file.

## File

`dist/refine-<version>.ankiaddon`, built by `py scripts/build.py`. The archive has the files at its top level (no parent folder) and no `__pycache__`.

AnkiWeb reads the supported Anki versions from `manifest.json` (`min_point_version` 250900 = 25.09, `max_point_version` 260903 = 26.09.3). After a new Anki release has been tested, raise `max_point_version` and upload again.

## Title

Refine – a modern, calm look for Anki

## Tags

`theme ui design dark-mode statistics heatmap`

## Support page

https://github.com/shreyanshsinghks/anki_refine/issues

## Description

Paste the HTML below. The images load from the GitHub repository. Each `src` names a release tag (`v0.3.0`), so the pictures stay matched to that release. Bump the tag when the screenshots change.

```html
<b>Refine</b> gives Anki's home screen, deck overview, answer bar and menus a cleaner, more modern look, in light and dark. It never changes your cards, your scheduling or your collection: everything it shows is read from Anki's own data, and nothing is written.

<img src="https://raw.githubusercontent.com/shreyanshsinghks/anki_refine/v0.3.0/docs/screenshots/dark_deck_browser.png">

<b>Home screen</b>
<ul>
<li>A sidebar with Decks, Stats, Browse, Add cards, Deck options, a light/dark switch and Sync, plus a search box (Ctrl+K).</li>
<li>A headline with the cards waiting and how long they'll take at your pace. Click any deck to see its numbers and a Study button.</li>
<li>Per deck: retention over the last 30 days, new cards left with the share already introduced, and a badge for leeches. Click the badge to open those cards in the Browser.</li>
<li>Today, a 26-week activity heatmap with streaks, and the next 7 days. Hover any day to see its figures.</li>
</ul>

<img src="https://raw.githubusercontent.com/shreyanshsinghks/anki_refine/v0.3.0/docs/screenshots/light_overview.png">

<b>Studying</b>
<ul>
<li>Deck overview with a "Last 14 days" chart (correct vs. Again).</li>
<li>Tinted Again / Good buttons with the interval inside. By default only these two are shown; keys 2 and 4 still answer Hard and Easy, and one setting brings all four back.</li>
<li>A one-line session summary when you finish a deck.</li>
<li>Statistics open inside the main window instead of a separate one.</li>
</ul>

<img src="https://raw.githubusercontent.com/shreyanshsinghks/anki_refine/v0.3.0/docs/screenshots/light_reviewer_answer.png">

<b>Settings</b>: Tools > Refine > Settings. Choose from eight accent colours and two densities, set motion, and turn each screen or home panel on or off. A master switch turns everything off at once.

<b>Safe by design</b>: if a screen fails, Refine turns just that screen off and Anki keeps working normally. Refine makes no network requests.

<b>Compatibility</b>: Anki 25.09 to 26.09.3. Tested on Windows. Other add-ons that restyle the same screens may conflict.

Source code, changelog and bug reports: <a href="https://github.com/shreyanshsinghks/anki_refine">github.com/shreyanshsinghks/anki_refine</a> (AGPL-3.0).
```

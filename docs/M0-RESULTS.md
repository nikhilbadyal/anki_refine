# M0 automated results

Generated 2026-10-24 09:17 by `scripts/devenv.py report`.

## Versions and engine

| | 25.09.5-pypi | 26.09.3-installed | 26.09.3-pypi |
|---|---|---|---|
| Anki | 25.09.5 | 26.09.3 | 26.09.3 |
| int_version | 250905 | 260903 | 260903 |
| Python | 3.11.4 | 3.13.15 | 3.11.4 |
| Qt / PyQt | 6.9.1 / 6.9.1 | 6.11.2 / 6.11.0 | 6.11.2 / 6.11.0 |
| QtWebEngine | 6.8.2 | 6.11.2 | 6.11.2 |
| Chromium (Qt API) | 122.0.6261.171 | 140.0.7339.225 | 140.0.7339.225 |
| Chrome (user agent) | 122.0.6261.171 | 140.0.0.0 | 140.0.0.0 |
| Chrome (DevTools /json/version) | Anki/3.11.4150.1013 | Anki/26.9.3.1 | Anki/3.11.4150.1013 |
| DevTools reachable after | 2.6 s | 1.7 s | 2.3 s |
| DevTools page targets | bottom toolbar, main webview, top toolbar | bottom toolbar, main webview, top toolbar | bottom toolbar, main webview, top toolbar |
| `layer_applies` | True | True | True |
| `layer_loses_to_unlayered` | True | True | True |
| `nesting` | True | True | True |
| supports `accent_color` | True | True | True |
| supports `color_mix` | True | True | True |
| supports `container_queries` | True | True | True |
| supports `focus_visible` | True | True | True |
| supports `has` | True | True | True |
| supports `is` | True | True | True |
| supports `mask_image` | True | True | True |
| supports `oklch` | True | True | True |
| supports `ruby_position` | True | True | True |
| supports `scrollbar_gutter` | True | True | True |
| supports `text_wrap_balance` | True | True | True |
| supports `where` | True | True | True |
| web export served | css/base.css → 200; config.json → 404 | css/base.css → 200; config.json → 404 | css/base.css → 200; config.json → 404 |
| style_did_init calls before main_window_did_init | 0 | 0 | 0 |
| style_did_init calls total | 2 | 2 | 2 |
| probe errors | 0 | 0 | 0 |
| exit code / wall time | 0 / 33.7 s | 0 / 32.7 s | 0 / 34.3 s |

## Toolbar height (px)

**25.09.5-pypi**

| phase | Qt widget height | document offsetHeight | innerHeight | content hook re-ran |
|---|---|---|---|---|
| 1_baseline | 37 | 455 | 37 |  |
| 2_after_late_css | 37 | 487 | 37 |  |
| 3_after_late_css_then_adjustHeightToFit | 69 | 487 | 69 |  |
| 4_late_css_removed | 37 | 455 | 37 |  |
| 5_render_time_css_via_draw | 69 | 487 | 69 | TopToolbar |
| 6_restored_via_draw | 37 | 455 | 37 | TopToolbar |

**26.09.3-installed**

| phase | Qt widget height | document offsetHeight | innerHeight | content hook re-ran |
|---|---|---|---|---|
| 1_baseline | 37 | 455 | 37 |  |
| 2_after_late_css | 37 | 487 | 37 |  |
| 3_after_late_css_then_adjustHeightToFit | 69 | 455 | 69 |  |
| 4_late_css_removed | 37 | 455 | 37 |  |
| 5_render_time_css_via_draw | 69 | 455 | 69 | TopToolbar |
| 6_restored_via_draw | 37 | 455 | 37 | TopToolbar |

**26.09.3-pypi**

| phase | Qt widget height | document offsetHeight | innerHeight | content hook re-ran |
|---|---|---|---|---|
| 1_baseline | 37 | 455 | 37 |  |
| 2_after_late_css | 37 | 487 | 37 |  |
| 3_after_late_css_then_adjustHeightToFit | 69 | 455 | 69 |  |
| 4_late_css_removed | 37 | 455 | 37 |  |
| 5_render_time_css_via_draw | 69 | 455 | 69 | TopToolbar |
| 6_restored_via_draw | 37 | 455 | 37 | TopToolbar |

## Theme toggle

**25.09.5-pypi** (original theme 0, night mode True)

| sample | night_mode | style_did_init calls (cum.) | content hook calls (cum.) | main `<html>` class | toolbar `<html>` class |
|---|---|---|---|---|---|
| before | True | 0 | 15 | `night-mode` | `night-mode` |
| after_flip | False | 1 | 15 | `` | `` |
| after_restore | True | 2 | 15 | `night-mode` | `night-mode` |

**26.09.3-installed** (original theme 0, night mode True)

| sample | night_mode | style_did_init calls (cum.) | content hook calls (cum.) | main `<html>` class | toolbar `<html>` class |
|---|---|---|---|---|---|
| before | True | 0 | 15 | `night-mode` | `night-mode` |
| after_flip | False | 1 | 15 | `` | `` |
| after_restore | True | 2 | 15 | `night-mode` | `night-mode` |

**26.09.3-pypi** (original theme 0, night mode True)

| sample | night_mode | style_did_init calls (cum.) | content hook calls (cum.) | main `<html>` class | toolbar `<html>` class |
|---|---|---|---|---|---|
| before | True | 0 | 15 | `night-mode` | `night-mode` |
| after_flip | False | 1 | 15 | `` | `` |
| after_restore | True | 2 | 15 | `night-mode` | `night-mode` |

## Day cutoff

**25.09.5-pypi**
```json
{
  "now_epoch_s": 1792813615,
  "day_cutoff": 1792881000,
  "day_cutoff_type": "int",
  "seconds_until_cutoff": 67384,
  "day_cutoff_local_iso": "2026-10-25T04:00:00+05:30",
  "sched_today_days_elapsed": 0,
  "col_crt": 1792794600,
  "days_crt_to_cutoff": 1.0,
  "rollover_hour": 4,
  "expected_next_rollover_epoch": 1792881000,
  "matches_next_local_rollover": true,
  "revlog_total": 2,
  "revlog_since_cutoff_minus_1d": 2,
  "revlog_time_ms_since_cutoff_minus_1d": 3928,
  "studied_today_string": "Studied ⁨1⁩ card\n⁨in ⁨3.93⁩ seconds⁩ today\n(⁨3.93⁩s/card)",
  "has_day_did_change_hook": true,
  "after_rollover_change": {
    "rollover_hour": 10,
    "day_cutoff": 1792816200
  },
  "restored_day_cutoff": 1792881000
}
```
**26.09.3-installed**
```json
{
  "now_epoch_s": 1792813545,
  "day_cutoff": 1792881000,
  "day_cutoff_type": "int",
  "seconds_until_cutoff": 67454,
  "day_cutoff_local_iso": "2026-10-25T04:00:00+05:30",
  "sched_today_days_elapsed": 0,
  "col_crt": 1792794600,
  "days_crt_to_cutoff": 1.0,
  "rollover_hour": 4,
  "expected_next_rollover_epoch": 1792881000,
  "matches_next_local_rollover": true,
  "revlog_total": 2,
  "revlog_since_cutoff_minus_1d": 2,
  "revlog_time_ms_since_cutoff_minus_1d": 3918,
  "studied_today_string": "Studied ⁨1⁩ card\n⁨in ⁨3.92⁩ seconds⁩ today\n(⁨3.92⁩s/card)",
  "has_day_did_change_hook": true,
  "after_rollover_change": {
    "rollover_hour": 10,
    "day_cutoff": 1792816200
  },
  "restored_day_cutoff": 1792881000
}
```
**26.09.3-pypi**
```json
{
  "now_epoch_s": 1792813580,
  "day_cutoff": 1792881000,
  "day_cutoff_type": "int",
  "seconds_until_cutoff": 67419,
  "day_cutoff_local_iso": "2026-10-25T04:00:00+05:30",
  "sched_today_days_elapsed": 0,
  "col_crt": 1792794600,
  "days_crt_to_cutoff": 1.0,
  "rollover_hour": 4,
  "expected_next_rollover_epoch": 1792881000,
  "matches_next_local_rollover": true,
  "revlog_total": 2,
  "revlog_since_cutoff_minus_1d": 2,
  "revlog_time_ms_since_cutoff_minus_1d": 3919,
  "studied_today_string": "Studied ⁨1⁩ card\n⁨in ⁨3.92⁩ seconds⁩ today\n(⁨3.92⁩s/card)",
  "has_day_did_change_hook": true,
  "after_rollover_change": {
    "rollover_hour": 10,
    "day_cutoff": 1792816200
  },
  "restored_day_cutoff": 1792881000
}
```

## Reviewer refresh paths

**25.09.5-pypi**

| path | content-hook contexts fired | same card | state before → after | window focused |
|---|---|---|---|---|
| `js_live_style_injection` | none | True | answer → answer | False |
| `reviewer.refresh_if_needed()` | none | True | answer → answer | False |
| `mw.reset()` | none | True | answer → answer | False |
| `mw.moveToState("review")` | Reviewer, ReviewerBottomBar | True | answer → question | False |

**26.09.3-installed**

| path | content-hook contexts fired | same card | state before → after | window focused |
|---|---|---|---|---|
| `js_live_style_injection` | none | True | answer → answer | False |
| `reviewer.refresh_if_needed()` | none | True | answer → answer | False |
| `mw.reset()` | none | True | answer → answer | False |
| `mw.moveToState("review")` | Reviewer, ReviewerBottomBar | True | answer → question | False |

**26.09.3-pypi**

| path | content-hook contexts fired | same card | state before → after | window focused |
|---|---|---|---|---|
| `js_live_style_injection` | none | True | answer → answer | True |
| `reviewer.refresh_if_needed()` | none | True | answer → answer | True |
| `mw.reset()` | none | True | answer → question | True |
| `mw.moveToState("review")` | Reviewer, ReviewerBottomBar | True | answer → question | True |

## Class / id inventory differences

- `deck_browser`: identical (24 classes/ids/data-attrs)
- `deck_browser_after_review`: identical (25 classes/ids/data-attrs)
- `deck_browser_flipped_theme`: identical (22 classes/ids/data-attrs)
- `deck_browser_bottom`: identical (9 classes/ids/data-attrs)
- `toolbar`: identical (18 classes/ids/data-attrs)
- `overview`: identical (13 classes/ids/data-attrs)
- `overview_bottom`: identical (9 classes/ids/data-attrs)
- `reviewer_question`: only in 25.09.5-pypi: #MJX-CHTML-styles
- `reviewer_answer`: only in 25.09.5-pypi: #MJX-CHTML-styles
- `reviewer_bottom_question`: identical (18 classes/ids/data-attrs)
- `reviewer_bottom_answer`: identical (16 classes/ids/data-attrs)

## Probe errors


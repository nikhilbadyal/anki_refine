"""Selector contract: the DOM hooks Refine's CSS will rely on must exist in
the captured HTML of every supported Anki version.

Fixtures are produced by `py scripts/devenv.py snapshot --all`. When Anki
changes a legacy screen, this test names the selector and version that broke.

Run: py -m unittest discover -s tests -t .
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from devtools.htmlinventory import inventory_file  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"

# screen -> selectors that must match at least one element
CONTRACT: dict[str, list[str]] = {
    "deck_browser": [
        "html[data-bs-theme]",
        "tr.deck",
        "tr.deck.current",
        "tr.top-level-drag-row",
        "td.decktd",
        "a.deck",
        "a.deck.filtered",
        "a.collapse",
        "th.count",
        "td.opts",
        "img.gears",
        "span.new-count",
        "span.review-count",
        "span.zero-count",
        "#studiedToday",
    ],
    "deck_browser_after_review": ["span.learn-count"],
    "deck_browser_bottom": ["#outer", "button"],
    "toolbar": [
        "a.hitem",
        "#decks",
        "#add",
        "#browse",
        "#stats",
        "#sync",
        ".left-tray",
        ".right-tray",
    ],
    "overview": [
        "button#study",
        "span.new-count",
        "span.learn-count",
        "span.review-count",
    ],
    "overview_bottom": ["#outer", "button"],
    "reviewer_question": ["#qa", "#_mark", "#_flag", "body.card"],
    "reviewer_bottom_question": [
        "button#ansbut",
        "#time",
        "td.stat",
        "span.new-count",
        "span.learn-count",
        "span.review-count",
    ],
    "reviewer_bottom_answer": [
        "button[data-ease=1]",
        "button[data-ease=2]",
        "button[data-ease=3]",
        "button[data-ease=4]",
        "button#defease",
        "span.nobold",
    ],
}

# theme state Anki toggles without re-rendering; Refine's tokens key off it
THEME_CONTRACT = {
    "deck_browser": "html.night-mode",  # captured in a dark-mode profile
}


def _versions() -> list[Path]:
    return sorted(p for p in FIXTURES.iterdir() if p.is_dir()) if FIXTURES.exists() else []


class SelectorContract(unittest.TestCase):
    def test_fixtures_present(self) -> None:
        self.assertTrue(_versions(), "no fixtures; run scripts/devenv.py snapshot --all")

    def test_contract(self) -> None:
        for version in _versions():
            for screen, selectors in CONTRACT.items():
                path = version / f"{screen}.html"
                with self.subTest(version=version.name, screen=screen):
                    self.assertTrue(path.exists(), f"missing snapshot {path}")
                    inv = inventory_file(path)
                    missing = [s for s in selectors if inv.matches(s) == 0]
                    self.assertEqual(missing, [], f"{version.name}/{screen}")

    def test_answer_button_count(self) -> None:
        for version in _versions():
            with self.subTest(version=version.name):
                inv = inventory_file(version / "reviewer_bottom_answer.html")
                self.assertEqual(inv.matches("button[data-ease]"), 4)

    def test_theme_classes_toggle(self) -> None:
        for version in _versions():
            for screen, sel in THEME_CONTRACT.items():
                with self.subTest(version=version.name, screen=screen):
                    dark = inventory_file(version / f"{screen}.html").matches(sel)
                    light = inventory_file(version / "deck_browser_flipped_theme.html").matches(sel)
                    # one capture is dark, the flipped one is light (or vice versa)
                    self.assertNotEqual(bool(dark), bool(light))


if __name__ == "__main__":
    unittest.main()

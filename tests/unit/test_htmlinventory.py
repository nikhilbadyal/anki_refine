from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from devtools.htmlinventory import inventory, parse_selector  # noqa: E402

HTML = """
<html class="night-mode" data-bs-theme="dark"><body class="card card1">
<table><tr class="deck current" id="1712"><td class=decktd>
<a class="deck filtered" href=#>Deck</a></td></tr></table>
<button data-ease="3" id="defease">Good</button><button data-ease="1">Again</button>
</body></html>
"""


class Selectors(unittest.TestCase):
    def setUp(self) -> None:
        self.inv = inventory(HTML)

    def test_compound(self) -> None:
        self.assertEqual(self.inv.matches("tr.deck.current"), 1)
        self.assertEqual(self.inv.matches("a.deck.filtered"), 1)
        self.assertEqual(self.inv.matches("tr.deck.missing"), 0)

    def test_attributes(self) -> None:
        self.assertEqual(self.inv.matches("button[data-ease]"), 2)
        self.assertEqual(self.inv.matches("button[data-ease=3]"), 1)
        self.assertEqual(self.inv.matches("button#defease[data-ease=3]"), 1)
        self.assertEqual(self.inv.matches("html[data-bs-theme=dark]"), 1)

    def test_numeric_ids_ignored_in_inventory(self) -> None:
        self.assertNotIn("1712", self.inv.ids())
        self.assertIn("defease", self.inv.ids())

    def test_rejects_descendant_combinator(self) -> None:
        with self.assertRaises(ValueError):
            parse_selector("tr .deck")


if __name__ == "__main__":
    unittest.main()

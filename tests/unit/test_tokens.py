"""Tests for refine.theme.tokens."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from refine.theme.palettes import ACCENTS  # noqa: E402
from refine.theme.tokens import CONTRAST_RULES, contrast, tokens  # noqa: E402

COLOR_KEYS = """bg surface surface-hover surface-active surface-sunken border border-strong
text text-muted text-faint accent accent-hover accent-fg accent-soft accent-text focus
new learn review again hard good easy again-soft hard-soft good-soft easy-soft
shadow-1 shadow-2 overlay primary-bg primary-fg primary-hover muted-count""".split()
OTHER_KEYS = """radius-s radius-m radius-l space-1 space-2 space-3 space-4 space-5 space-6 row-pad
font-ui font-display font-mono font-jp text-xs text-s text-m text-l text-xl text-2xl text-3xl
text-hero dur ease""".split()


class ContrastTests(unittest.TestCase):
    def test_known(self):
        self.assertAlmostEqual(contrast("#000000", "#FFFFFF"), 21.0, places=3)
        self.assertAlmostEqual(contrast("#FFF", "#000"), 21.0, places=3)
        self.assertAlmostEqual(contrast("#336699", "#336699"), 1.0, places=6)

    def test_rgba_composited(self):
        self.assertAlmostEqual(contrast("rgba(0, 0, 0, 1)", "#FFFFFF"), 21.0, places=3)
        self.assertAlmostEqual(contrast("rgba(255, 255, 255, 0.5)", "#000000"),
                               contrast("#808080", "#000000"), places=1)


class TokenTests(unittest.TestCase):
    def test_rules_all_combinations(self):
        failures = []
        for night in (False, True):
            for acc in ACCENTS:
                for dens in ("comfortable", "compact"):
                    t = tokens(night, acc, dens)
                    for fg, bg, mn in CONTRAST_RULES:
                        r = contrast(t[fg], t[bg])
                        if r < mn:
                            failures.append(
                                "night=%s %s/%s %s on %s (%s on %s) %.2f < %.1f" % (
                                    night, acc, dens, fg, bg, t[fg], t[bg], r, mn))
        self.assertEqual(failures, [], "\n".join(failures))

    def test_all_keys(self):
        for night in (False, True):
            for acc in ACCENTS:
                for dens in ("comfortable", "compact"):
                    t = tokens(night, acc, dens)
                    for k in COLOR_KEYS + OTHER_KEYS:
                        self.assertIn(k, t, (night, acc, dens, k))
                    for k in COLOR_KEYS:
                        self.assertTrue(t[k], k)

    def test_density(self):
        c = tokens(False, "jade", "comfortable")
        k = tokens(False, "jade", "compact")
        self.assertEqual(c["space-1"], k["space-1"])
        for i in range(2, 7):
            self.assertLess(int(k["space-%d" % i][:-2]), int(c["space-%d" % i][:-2]))
        self.assertEqual((c["row-pad"], k["row-pad"]), ("8px", "5px"))

    def test_fallbacks(self):
        self.assertEqual(tokens(False, "nope", "huge"),
                         tokens(False, "jade", "comfortable"))

    def test_accent_wiring(self):
        self.assertEqual(tokens(False, "blue", "comfortable")["accent"], ACCENTS["blue"].light)
        self.assertEqual(tokens(True, "blue", "comfortable")["accent"], ACCENTS["blue"].dark)
        self.assertEqual(list(ACCENTS)[0], "jade")


if __name__ == "__main__":
    unittest.main()

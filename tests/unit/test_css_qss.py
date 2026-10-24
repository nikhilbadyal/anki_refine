"""Tests for refine.theme.css and refine.theme.qss."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from refine.theme import css, qss  # noqa: E402
from refine.theme.tokens import tokens  # noqa: E402


class CssTests(unittest.TestCase):
    def test_root_css(self):
        out = css.root_css("jade", "comfortable")
        self.assertIn(":root.refine{", out)
        self.assertIn(":root.refine.night-mode{", out)
        for night in (False, True):
            for k in tokens(night, "jade", "comfortable"):
                self.assertIn("--rf-%s:" % k, out)
        for v in ("--canvas:", "--canvas-elevated:", "--fg:", "--fg-subtle:",
                  "--border:", "--border-subtle:"):
            self.assertIn(v, out)

    def test_style_tag(self):
        t = css.style_tag("blue", "compact")
        self.assertTrue(t.startswith('<style id="rf-tokens">'))
        self.assertTrue(t.endswith("</style>"))

    def test_live_js(self):
        js = css.live_update_js("jade", "comfortable")
        self.assertIn(css.STYLE_ID, js)
        self.assertNotIn("</script", js.lower())
        self.assertTrue(js.startswith("(function(){"))
        self.assertTrue(js.endswith("})();"))
        self.assertEqual(js.count("("), js.count(")"))


class QssTests(unittest.TestCase):
    def setUp(self):
        self.block = qss.render(tokens(False, "jade", "comfortable"))

    def test_render(self):
        self.assertTrue(self.block.startswith(qss.MARK_BEGIN))
        self.assertTrue(self.block.endswith(qss.MARK_END))
        for s in ("QMenu", "QMenuBar", "QToolTip", "QScrollBar", "QLineEdit:focus"):
            self.assertIn(s, self.block)
        self.assertNotIn("var(", self.block)
        self.assertNotIn("--rf-", self.block)
        self.assertEqual(self.block.count("{"), self.block.count("}"))

    def test_splice_twice(self):
        base = "QWidget { color: red; }\n"
        once = qss.splice(base, self.block)
        twice = qss.splice(once, qss.render(tokens(True, "jade", "comfortable")))
        self.assertEqual(twice.count(qss.MARK_BEGIN), 1)
        self.assertEqual(twice.count(qss.MARK_END), 1)
        self.assertTrue(twice.startswith(base))
        self.assertEqual(qss.splice(once, self.block), once)

    def test_strip(self):
        base = "QWidget { color: red; }\n"
        once = qss.splice(base, self.block)
        self.assertEqual(qss.strip(once), base)
        self.assertEqual(qss.strip(qss.strip(once)), base)
        self.assertEqual(qss.strip(base), base)

    def test_splice_empty(self):
        out = qss.splice("", self.block)
        self.assertIn(qss.MARK_BEGIN, out)
        self.assertEqual(qss.strip(out), "")


if __name__ == "__main__":
    unittest.main()

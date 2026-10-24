"""Tests for refine.guard."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import refine.guard as G  # noqa: E402


def boom(*a, **k):
    raise ValueError("bad")


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.disabled = []
        self.g = G.Guard(lambda sid, tb: self.disabled.append((sid, tb)), limit=3)

    def test_normal_path(self):
        w = self.g.wrap("a", lambda x, y=1: x + y)
        self.assertEqual(w(1, y=2), 3)
        self.assertEqual(self.g.errors(), {})

    def test_wrapped_attr(self):
        def f():
            return 1
        self.assertIs(self.g.wrap("a", f).__wrapped__, f)

    def test_error_returns_none(self):
        with self.assertLogs("refine", "ERROR"):
            self.assertIsNone(self.g.wrap("a", boom)())
        self.assertIn("ValueError", self.g.errors()["a"][0])

    def test_filter_returns_first_arg(self):
        w = self.g.wrap("a", boom, is_filter=True)
        with self.assertLogs("refine", "ERROR"):
            self.assertEqual(w("html", 2), "html")

    def test_disable_once_at_limit(self):
        w = self.g.wrap("a", boom)
        with self.assertLogs("refine", "ERROR"):
            for _ in range(6):
                w()
        self.assertEqual(len(self.disabled), 1)
        self.assertEqual(self.disabled[0][0], "a")
        self.assertIn("ValueError", self.disabled[0][1])
        self.assertTrue(self.g.is_disabled("a"))
        self.assertFalse(self.g.is_disabled("b"))

    def test_disabled_passthrough(self):
        calls = []
        w = self.g.wrap("a", boom)
        with self.assertLogs("refine", "ERROR"):
            for _ in range(3):
                w()
        ok = self.g.wrap("a", lambda x: calls.append(x) or "r", is_filter=True)
        self.assertEqual(ok("in"), "in")
        self.assertEqual(calls, [])
        self.assertIsNone(self.g.wrap("a", lambda: 1)())

    def test_errors_capped(self):
        g = G.Guard(lambda s, t: None, limit=1000)
        w = g.wrap("a", boom)
        with self.assertLogs("refine", "ERROR"):
            for _ in range(25):
                w()
        self.assertEqual(len(g.errors()["a"]), 10)

    def test_reset(self):
        w = self.g.wrap("a", boom)
        with self.assertLogs("refine", "ERROR"):
            for _ in range(3):
                w()
            self.g.reset("a")
            self.assertFalse(self.g.is_disabled("a"))
            self.assertEqual(self.g.errors(), {})
            for _ in range(3):
                w()
        self.assertEqual(len(self.disabled), 2)
        self.g.reset()
        self.assertFalse(self.g.is_disabled("a"))

    def test_on_disable_exception_swallowed(self):
        def bad(s, t):
            raise RuntimeError
        g = G.Guard(bad, limit=1)
        with self.assertLogs("refine", "ERROR"):
            self.assertIsNone(g.wrap("a", boom)())


if __name__ == "__main__":
    unittest.main()

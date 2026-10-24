"""Tests for refine.log."""

from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import refine.log as L  # noqa: E402


class LogTests(unittest.TestCase):
    def tearDown(self):
        lg = logging.getLogger("refine")
        for h in list(lg.handlers):
            h.close()
            lg.removeHandler(h)

    def test_file_created_and_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            log_dir = Path(d) / "logs"
            lg = L.setup(log_dir)
            L.setup(log_dir)
            self.assertEqual(len(lg.handlers), 1)
            self.assertFalse(lg.propagate)
            self.assertEqual(lg.level, logging.INFO)
            lg.info("hello there")
            for h in lg.handlers:
                h.flush()
            self.assertTrue((log_dir / "refine.log").exists())
            self.assertIn("hello there", L.recent(log_dir))
            self.tearDown()

    def test_none_gives_null_handler(self):
        lg = L.setup(None)
        L.setup(None)
        self.assertEqual(len(lg.handlers), 1)
        self.assertIsInstance(lg.handlers[0], logging.NullHandler)

    def test_recent_missing_and_tail(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(L.recent(Path(d)), "")
            (Path(d) / "refine.log").write_text(
                "\n".join(str(i) for i in range(10)), "utf-8")
            self.assertEqual(L.recent(Path(d), 3), "7\n8\n9")


if __name__ == "__main__":
    unittest.main()

"""Tests for refine.config."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import refine.config as C  # noqa: E402


class NormalizeTests(unittest.TestCase):
    def test_none_empty_garbage(self):
        for raw in (None, {}, [], "x", 5, object()):
            self.assertEqual(C.normalize(raw), C.DEFAULTS)

    def test_fresh_dict(self):
        a = C.normalize(None)
        a["surfaces"]["toolbar"] = False
        self.assertTrue(C.DEFAULTS["surfaces"]["toolbar"])
        self.assertTrue(C.normalize(None)["surfaces"]["toolbar"])

    def test_unknown_keys_dropped(self):
        out = C.normalize({"zzz": 1, "surfaces": {"nope": True}, "home": {"q": 1}})
        self.assertEqual(out, C.DEFAULTS)

    def test_bad_values(self):
        out = C.normalize({"accent": "pink", "density": 3, "enabled": "yes",
                           "surfaces": {"toolbar": "no", "reviewer": False},
                           "reviewer": "x", "home": {"hero": 0, "today": False}})
        self.assertEqual(out["accent"], "jade")
        self.assertEqual(out["density"], "comfortable")
        self.assertTrue(out["enabled"])
        self.assertTrue(out["surfaces"]["toolbar"])
        self.assertFalse(out["surfaces"]["reviewer"])
        self.assertTrue(out["reviewer"]["ease_colors"])
        self.assertTrue(out["home"]["hero"])
        self.assertFalse(out["home"]["today"])

    def test_unhashable_accent(self):
        self.assertEqual(C.normalize({"accent": ["x"]})["accent"], "jade")

    def test_valid_values_kept(self):
        out = C.normalize({"accent": "teal", "density": "compact", "enabled": False})
        self.assertEqual((out["accent"], out["density"], out["enabled"]),
                         ("teal", "compact", False))

    def test_old_schema(self):
        out = C.normalize({"schema_version": 0, "accent": "blue"})
        self.assertEqual(out["schema_version"], C.SCHEMA_VERSION)
        self.assertEqual(out["accent"], "blue")
        out = C.normalize({"schema_version": "banana"})
        self.assertEqual(out["schema_version"], C.SCHEMA_VERSION)

    def test_ids(self):
        from refine.theme.palettes import ACCENTS
        self.assertEqual(C.ACCENT_IDS, tuple(ACCENTS))


class StoreTests(unittest.TestCase):
    def make(self, initial=None, write=None):
        self.written = []
        w = write or self.written.append
        return C.ConfigStore(lambda: initial, w)

    def test_get_is_copy(self):
        s = self.make()
        s.get()["accent"] = "rose"
        self.assertEqual(s.value("accent"), "jade")

    def test_set_and_value(self):
        s = self.make()
        s.set("surfaces.toolbar", False)
        self.assertIs(s.value("surfaces.toolbar"), False)
        self.assertEqual(len(self.written), 1)
        self.assertIs(self.written[0]["surfaces"]["toolbar"], False)
        self.assertIsNone(s.value("nope.x"))

    def test_invalid_set_ignored(self):
        s = self.make()
        s.set("accent", "pink")
        self.assertEqual(s.value("accent"), "jade")

    def test_update_single_write_notify(self):
        s = self.make()
        calls = []
        s.subscribe(lambda cfg, ch: calls.append(ch))
        s.update({"accent": "blue", "density": "compact"})
        self.assertEqual(len(self.written), 1)
        self.assertEqual(calls, [frozenset({"accent", "density"})])

    def test_notify_only_on_change(self):
        s = self.make()
        calls = []
        s.subscribe(lambda cfg, ch: calls.append(ch))
        s.set("accent", "jade")
        self.assertEqual(calls, [])
        s.set("accent", "rose")
        self.assertEqual(calls, [frozenset({"accent"})])

    def test_reset(self):
        s = self.make({"accent": "rose"})
        calls = []
        s.subscribe(lambda cfg, ch: calls.append((cfg, ch)))
        s.reset()
        self.assertEqual(s.get(), C.DEFAULTS)
        self.assertEqual(calls[0][1], frozenset({"accent"}))
        self.assertEqual(len(self.written), 1)

    def test_reload(self):
        data = {"accent": "blue"}
        s = C.ConfigStore(lambda: data, lambda c: None)
        data["accent"] = "rose"
        calls = []
        s.subscribe(lambda cfg, ch: calls.append(ch))
        s.reload()
        self.assertEqual(s.value("accent"), "rose")
        self.assertEqual(calls, [frozenset({"accent"})])

    def test_write_failure_swallowed(self):
        def boom(c):
            raise OSError("disk")
        s = self.make(write=boom)
        s.set("accent", "rose")
        self.assertEqual(s.value("accent"), "rose")

    def test_subscriber_exception_swallowed(self):
        s = self.make()
        calls = []

        def bad(cfg, ch):
            raise RuntimeError("x")
        s.subscribe(bad)
        s.subscribe(lambda cfg, ch: calls.append(ch))
        s.set("accent", "rose")
        self.assertEqual(len(calls), 1)

    def test_read_failure(self):
        def boom():
            raise ValueError
        s = C.ConfigStore(boom, lambda c: None)
        self.assertEqual(s.get(), C.DEFAULTS)




class CardsSection(unittest.TestCase):
    def test_cards_default_off_and_normalized(self) -> None:
        from refine import config

        self.assertEqual(config.normalize(None)["cards"], {"japanese": False, "furigana_hover": False})
        got = config.normalize({"cards": {"japanese": True, "furigana_hover": "yes", "bogus": 1}})
        self.assertEqual(got["cards"], {"japanese": True, "furigana_hover": False})


class DailyGoal(unittest.TestCase):
    def test_goal_validation(self) -> None:
        from refine import config

        self.assertEqual(config.normalize(None)["daily_goal"], 0)
        self.assertEqual(config.normalize({"daily_goal": 150})["daily_goal"], 150)
        for bad in (-1, 10**6, "100", True, 3.5, None):
            self.assertEqual(config.normalize({"daily_goal": bad})["daily_goal"], 0, bad)


class DeckClick(unittest.TestCase):
    def test_deck_click_values(self) -> None:
        from refine import config

        self.assertEqual(config.normalize(None)["deck_click"], "select")
        self.assertEqual(config.normalize({"deck_click": "overview"})["deck_click"], "overview")
        self.assertEqual(config.normalize({"deck_click": "jump"})["deck_click"], "select")


class Motion(unittest.TestCase):
    def test_motion_values(self) -> None:
        from refine import config

        self.assertEqual(config.normalize(None)["motion"], "smooth")
        self.assertEqual(config.normalize({"motion": "reduced"})["motion"], "reduced")
        self.assertEqual(config.normalize({"motion": "fast"})["motion"], "smooth")


if __name__ == "__main__":
    unittest.main()

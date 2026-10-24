import datetime
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from refine import home  # noqa: E402
from refine.home import DAY, HomeStats, Totals  # noqa: E402


def node(new=0, learn=0, review=0, children=(), deck_id=1, name="d"):
    return NS(new_count=new, learn_count=learn, review_count=review, children=list(children), deck_id=deck_id, name=name)


class FakeDB:
    """Canned rows; dict values are matched by substring of the SQL."""

    def __init__(self, all_rows=None, scalar=None, first=None):
        self.all_rows, self.scalar_val, self.first_val = all_rows or [], scalar, first
        self.calls = []

    @staticmethod
    def _pick(src, sql, default):
        if isinstance(src, dict):
            for k, v in src.items():
                if k in sql:
                    return v
            return default
        return src

    def all(self, sql, *a):
        self.calls.append(("all", sql, a))
        return self._pick(self.all_rows, sql, [])

    def scalar(self, sql, *a):
        self.calls.append(("scalar", sql, a))
        return self._pick(self.scalar_val, sql, None)

    def first(self, sql, *a):
        self.calls.append(("first", sql, a))
        return self.first_val


def fake_col(db, cutoff=10_000_000, today=100):
    return NS(sched=NS(day_cutoff=cutoff, today=today), db=db)


class Streaks(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(home.streaks([]), (0, 0))

    def test_all_zero(self):
        self.assertEqual(home.streaks([0, 0, 0]), (0, 0))

    def test_today_zero_counts_from_yesterday(self):
        self.assertEqual(home.streaks([1, 1, 1, 0]), (3, 3))

    def test_today_studied(self):
        self.assertEqual(home.streaks([0, 2, 3]), (2, 2))

    def test_best_vs_current(self):
        self.assertEqual(home.streaks([1, 1, 1, 1, 0, 0, 1, 1]), (2, 4))

    def test_gap_yesterday_breaks_current(self):
        self.assertEqual(home.streaks([1, 1, 0, 0]), (0, 2))


class Formatting(unittest.TestCase):
    def test_duration(self):
        f = home.fmt_duration
        self.assertEqual(f(0), "0s")
        self.assertEqual(f(59_000), "59s")
        self.assertEqual(f(60_000), "1 min")
        self.assertEqual(f(59 * 60_000), "59 min")
        self.assertEqual(f(60 * 60_000), "1 h")
        self.assertEqual(f(125 * 60_000), "2 h 5 min")

    def test_int(self):
        self.assertEqual(home.fmt_int(0), "0")
        self.assertEqual(home.fmt_int(1234567), "1,234,567")


class TotalsTests(unittest.TestCase):
    def test_empty(self):
        t = home.totals(node())
        self.assertEqual((t.new, t.learn, t.review, t.decks, t.due), (0, 0, 0, 0, 0))

    def test_tree(self):
        tree = node(children=[node(1, 2, 3, children=[node(), node()]), node(10, 0, 5)])
        t = home.totals(tree)
        # only top-level counts are summed (children counts are already rolled up)
        self.assertEqual((t.new, t.learn, t.review), (11, 2, 8))
        self.assertEqual(t.decks, 4)
        self.assertEqual(t.due, 21)

    def test_no_children_attr(self):
        self.assertEqual(home.totals(object()).decks, 0)


class Hero(unittest.TestCase):
    D = datetime.date(2026, 3, 5)

    def test_escapes_name(self):
        out = home.hero_html(Totals(new=1, review=2), '<b>x</b>&"', 7, self.D)
        self.assertNotIn("<b>x</b>", out)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;&amp;&quot;", out)
        self.assertIn("refine:deck_browser:study:7", out)
        self.assertIn("3 cards waiting", out)
        self.assertIn("Thursday, March 5", out)

    def test_singular(self):
        self.assertIn("1 card waiting", home.hero_html(Totals(new=1), "a", 1, self.D))

    def test_all_caught_up_no_button(self):
        out = home.hero_html(Totals(), "Default", 1, self.D)
        self.assertIn("All caught up", out)
        self.assertNotIn("<button", out)

    def test_no_target_no_button(self):
        self.assertNotIn("<button", home.hero_html(Totals(new=3), None, None, self.D))


class Panels(unittest.TestCase):
    def test_forecast_zeros(self):
        s = HomeStats(forecast=[0] * 7)
        out = home.forecast_html(s, datetime.date(2026, 3, 5))
        self.assertEqual(out.count("height:4%"), 7)
        self.assertEqual(out.count("rf-bar-now"), 1)
        self.assertIn(">Th<", out)

    def test_forecast_dominant_first_day(self):
        s = HomeStats(forecast=[400, 1, 4, 0, 100, 0, 0])
        out = home.forecast_html(s, datetime.date(2026, 3, 5))
        self.assertIn("height:100%", out)
        self.assertIn("height:8%", out)  # sqrt(1/400)*100 = 5 -> min 8
        self.assertIn("height:10%", out)  # sqrt(4/400)*100
        self.assertIn("height:50%", out)  # sqrt(100/400)*100
        self.assertIn("height:4%", out)  # zeros

    def test_forecast_empty(self):
        self.assertIn("rf-bars", home.forecast_html(HomeStats()))

    def test_today_notes(self):
        t0 = Totals()
        self.assertIn("Nothing due today.", home.today_html(HomeStats(), t0))
        self.assertIn("Done for today.", home.today_html(HomeStats(today_cards=5, today_ms=61_000), t0))
        out = home.today_html(HomeStats(today_cards=5, forecast=[0, 1234]), Totals(review=5))
        self.assertIn("1,234 for tomorrow", out)
        self.assertIn('aria-valuenow="50"', out)
        self.assertIn("1 min", home.today_html(HomeStats(today_cards=1, today_ms=61_000), t0))
        self.assertIn("card studied", home.today_html(HomeStats(today_cards=1), t0))

    def test_today_no_forecast(self):
        self.assertIn("for tomorrow", home.today_html(HomeStats(), Totals(new=1)))

    def test_activity_levels(self):
        s = HomeStats(activity=[0, 1, 25, 26, 75, 100], streak=1, best_streak=3)
        out = home.activity_html(s)
        for lvl in range(5):
            self.assertIn(f'class="rf-l{lvl}"', out)
        self.assertIn('class="rf-l1" title="1 review"', out)
        self.assertIn('class="rf-l1" title="25 reviews"', out)
        self.assertIn('class="rf-l2" title="26 reviews"', out)
        self.assertIn('class="rf-l4" title="100 reviews"', out)
        self.assertIn("Streak 1 day<", out)
        self.assertIn("Best 3", out)

    def test_activity_empty(self):
        out = home.activity_html(HomeStats(activity=[0, 0], streak=2))
        self.assertEqual(out.count('class="rf-l0"'), 2)
        self.assertIn("Streak 2 days", out)
        self.assertIn("rf-heat", home.activity_html(HomeStats()))

    def test_pace(self):
        self.assertEqual(home.pace_text(Totals(), HomeStats(avg_ms=5000)), "")
        self.assertEqual(home.pace_text(Totals(new=5), HomeStats(avg_ms=0)), "")
        self.assertIn("10 min at your pace", home.pace_text(Totals(new=60), HomeStats(avg_ms=10_000)))

    def test_side_placeholder(self):
        out = home.side_placeholder()
        for c in ("rf-today", "rf-activity", "rf-forecast"):
            self.assertIn(c, out)


class Queries(unittest.TestCase):
    CUT = 10_000_000

    def test_daily_counts_buckets(self):
        db = FakeDB(all_rows=[(0, 3), (9, 4), (10, 5), (-1, 9)])
        out = home.daily_counts(fake_col(db, self.CUT), 10)
        self.assertEqual(out, [3, 0, 0, 0, 0, 0, 0, 0, 0, 4])
        _, sql, args = db.calls[0]
        self.assertIn("type not in (4, 5)", sql)
        self.assertEqual(args, (self.CUT - 10 * DAY, (self.CUT - 10 * DAY) * 1000))

    def test_forecast(self):
        db = FakeDB(all_rows=[(98, 2), (100, 3), (101, 4), (106, 1)], scalar=5)
        out = home.forecast(fake_col(db, today=100))
        self.assertEqual(out, [10, 4, 0, 0, 0, 0, 1])
        self.assertEqual(db.calls[0][2], (107,))
        self.assertEqual(db.calls[1][2], (self.CUT,))

    def test_forecast_none_scalar(self):
        self.assertEqual(home.forecast(fake_col(FakeDB(all_rows=[], scalar=None))), [0] * 7)

    def test_collect(self):
        n = home.STREAK_DAYS
        db = FakeDB(
            all_rows={"from revlog": [(n - 1, 3), (n - 2, 1), (n - 3, 1)], "from cards": [(100, 2)]},
            scalar={"avg(time)": 4500.0, "from cards": 1},
            first=(7, 61_000),
        )
        s = home.collect(fake_col(db, self.CUT, 100))
        self.assertEqual((s.today_cards, s.today_ms), (7, 61_000))
        self.assertEqual(len(s.activity), home.ACTIVITY_DAYS)
        self.assertEqual(s.activity[-3:], [1, 1, 3])
        self.assertEqual((s.streak, s.best_streak), (3, 3))
        self.assertEqual(s.forecast[0], 3)
        self.assertEqual(s.avg_ms, 4500.0)
        revlog_sql = [c[1] for c in db.calls if "from revlog" in c[1]]
        self.assertEqual(len(revlog_sql), 3)
        for sql in revlog_sql:
            self.assertIn("type not in (4, 5)", sql)
        self.assertEqual(db.calls[0][2], ((self.CUT - DAY) * 1000,))


class Onboarding(unittest.TestCase):
    def test_uses_deck_browser_commands(self) -> None:
        out = home.onboarding_html()
        for cmd in ("create", "import", "shared"):
            self.assertIn(f"pycmd('{cmd}')", out)
        self.assertIn("rf-onboarding", out)
        self.assertNotIn("caught up", out)


if __name__ == "__main__":
    unittest.main()

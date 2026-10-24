import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from refine import deck_stats as ds  # noqa: E402

TODAY = datetime.date(2026, 10, 24)


class SeriesTests(unittest.TestCase):
    def test_fourteen_days_oldest_first(self):
        s = ds.build_series([], TODAY)
        self.assertEqual(len(s.days), 14)
        self.assertEqual(s.days[-1].date, TODAY)
        self.assertEqual(s.days[0].date, datetime.date(2026, 10, 11))

    def test_bucketing_and_stacking(self):
        s = ds.build_series([(13, 10, 3, 8, 6), (0, 4, 0, 4, 4), (14, 99, 9, 9, 9), (-1, 5, 5, 5, 5)], TODAY)
        self.assertEqual((s.days[13].total, s.days[13].again, s.days[13].correct), (10, 3, 7))
        self.assertEqual(s.days[0].correct, 4)
        self.assertEqual(s.total, 14)  # out-of-range rows ignored

    def test_average_and_percent(self):
        s = ds.build_series([(13, 140, 10, 100, 88), (12, 448, 0, 0, 0)], TODAY)
        self.assertEqual(s.total, 588)
        self.assertEqual(s.average, 42)
        self.assertEqual(s.percent_correct, 88)
        self.assertEqual(ds.summary_text(s), "Avg 42 reviews/day · 88% correct")

    def test_zero_handling(self):
        s = ds.build_series([], TODAY)
        self.assertEqual(s.average, 0)
        self.assertIsNone(s.percent_correct)
        self.assertEqual(ds.summary_text(s), "")
        self.assertIn("No reviews in the last 14 days", ds.chart_html(s))
        self.assertNotIn("rf-dc-chart", ds.chart_html(s))

    def test_no_review_type_answers_omits_percent(self):
        s = ds.build_series([(13, 5, 1, 0, 0)], TODAY)
        self.assertEqual(ds.summary_text(s), "Avg 0.4 reviews/day")

    def test_labels(self):
        d = ds.Day(datetime.date(2026, 10, 20), total=34, again=3)
        self.assertEqual(ds.day_title(d), "Oct 20: 34 reviews, 3 Again")
        self.assertEqual(ds.day_title(ds.Day(TODAY, total=1, again=0), True), "Today: 1 review, 0 Again")
        self.assertEqual(ds.day_title(ds.Day(TODAY)), "Oct 24: no reviews")
        self.assertEqual(ds.day_label(d, False), "Tue")
        self.assertEqual(ds.day_label(d, True), "Today")


class MarkupTests(unittest.TestCase):
    def test_chart(self):
        s = ds.build_series([(13, 10, 3, 10, 7), (12, 5, 0, 5, 5)], TODAY)
        out = ds.chart_html(s)
        self.assertEqual(out.count('class="rf-dc-col'), 14)
        self.assertIn('role="img"', out)
        self.assertIn("aria-label=", out)
        self.assertIn('title="Today: 10 reviews, 3 Again"', out)
        self.assertEqual(out.count("rf-dc-stub"), 12)
        self.assertIn("flex-grow:3", out)
        self.assertIn("flex-grow:7", out)
        self.assertIn("height:100%", out)

    def test_panel_placeholder_and_filled(self):
        self.assertIn("pycmd('refine:overview:chart:5')", ds.panel_html(5, None))
        filled = ds.panel_html(5, "<b>x</b>")
        self.assertNotIn("pycmd", filled)
        self.assertIn("<b>x</b>", filled)


if __name__ == "__main__":
    unittest.main()

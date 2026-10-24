"""Per-deck "Last 14 days" figures for the deck overview.

Same conventions as home.py: a day is the 86400 s before the scheduler's
day_cutoff, manual (4) and rescheduled (5) revlog entries are not reviews, and
the percentage uses review answers (type 1) like Anki's true retention. Cards
in a filtered deck count toward their home deck (cards.odid). The query takes
a Collection and runs in a background QueryOp; everything else is pure.
"""

from __future__ import annotations

import datetime
import html
from dataclasses import dataclass, field
from typing import Any, Iterable

DAY = 86400
DAYS = 14
EXCLUDED_TYPES = "(4, 5)"  # same definition as home.EXCLUDED_TYPES


@dataclass
class Day:
    date: datetime.date
    total: int = 0  # all answers except manual / rescheduled entries
    again: int = 0  # of those, ease = 1
    reviews: int = 0  # review-type answers (revlog type 1)
    passed: int = 0  # of those, ease > 1

    @property
    def correct(self) -> int:
        return self.total - self.again


@dataclass
class Series:
    days: list[Day] = field(default_factory=list)  # oldest .. today

    @property
    def total(self) -> int:
        return sum(d.total for d in self.days)

    @property
    def average(self) -> float:
        return self.total / len(self.days) if self.days else 0.0

    @property
    def percent_correct(self) -> int | None:
        reviews = sum(d.reviews for d in self.days)
        if not reviews:
            return None
        return round(100 * sum(d.passed for d in self.days) / reviews)


# --------------------------------------------------------------- queries


def deck_ids(col: Any, deck_id: int) -> list[int]:
    ids = [int(i) for i in col.decks.deck_and_child_ids(deck_id)]
    return ids or [int(deck_id)]


def query_rows(col: Any, deck_id: int, days: int = DAYS) -> list[tuple[int, int, int, int, int]]:
    """(day index, answers, again, review answers, passed review answers) per
    day with activity; index 0 is the oldest of `days`, days-1 is today."""
    cutoff = col.sched.day_cutoff
    start = cutoff - days * DAY
    ids = ", ".join(str(i) for i in deck_ids(col, deck_id))
    dyn = bool(col.decks.get(deck_id) and col.decks.get(deck_id).get("dyn"))
    if dyn:
        scope = f"c.did in ({ids})"
    else:
        scope = f"((c.odid != 0 and c.odid in ({ids})) or (c.odid = 0 and c.did in ({ids})))"
    rows = col.db.all(
        f"select cast((r.id / 1000 - ?) / {DAY} as int) as d, count(), "
        "coalesce(sum(r.ease = 1), 0), coalesce(sum(r.type = 1), 0), "
        "coalesce(sum(r.type = 1 and r.ease > 1), 0) "
        "from revlog r join cards c on c.id = r.cid "
        f"where r.id > ? and r.type not in {EXCLUDED_TYPES} and {scope} group by d",
        start,
        start * 1000,
    )
    return [tuple(int(x) for x in row) for row in rows]  # type: ignore[misc]


def today_date(col: Any) -> datetime.date:
    """The calendar date the scheduler considers today."""
    return datetime.datetime.fromtimestamp(col.sched.day_cutoff - 1).date()


def collect(col: Any, deck_id: int) -> Series:
    return build_series(query_rows(col, deck_id), today_date(col))


# ------------------------------------------------------------------ pure


def build_series(rows: Iterable[tuple[int, int, int, int, int]], today: datetime.date, days: int = DAYS) -> Series:
    out = [Day(today - datetime.timedelta(days=days - 1 - i)) for i in range(days)]
    for d, total, again, reviews, passed in rows:
        if 0 <= d < days:
            day = out[d]
            day.total += total
            day.again += again
            day.reviews += reviews
            day.passed += passed
    return Series(out)


def fmt_int(n: int) -> str:
    return f"{n:,}"


def plural(n: int, word: str) -> str:
    return f"{fmt_int(n)} {word}{'' if n == 1 else 's'}"


def fmt_average(avg: float) -> str:
    return fmt_int(round(avg)) if avg >= 10 else f"{avg:.1f}".rstrip("0").rstrip(".")


def summary_text(s: Series) -> str:
    """"Avg 42 reviews/day · 88% correct"; empty when there is nothing."""
    if not s.total:
        return ""
    text = f"Avg {fmt_average(s.average)} reviews/day"
    pct = s.percent_correct
    if pct is not None:
        text += f" · {pct}% correct"
    return text


def day_title(d: Day, is_today: bool = False) -> str:
    """Tooltip, e.g. "Oct 20: 34 reviews, 3 Again"."""
    name = "Today" if is_today else f"{d.date.strftime('%b')} {d.date.day}"
    if not d.total:
        return f"{name}: no reviews"
    return f"{name}: {plural(d.total, 'review')}, {d.again} Again"


def aria_label(s: Series) -> str:
    if not s.total:
        return "No reviews in the last 14 days"
    busiest = max(s.days, key=lambda d: d.total)
    return (
        f"Reviews per day, last {len(s.days)} days. {summary_text(s)}. "
        f"Busiest day {busiest.date.strftime('%b')} {busiest.date.day} with {plural(busiest.total, 'review')}."
    )


def day_label(d: Day, is_today: bool) -> str:
    return "Today" if is_today else d.date.strftime("%a")[:3]


def empty_html() -> str:
    return '<p class="rf-dc-empty">No reviews in the last 14 days</p>'


def chart_html(s: Series) -> str:
    """Body of the panel (below its heading): chart plus summary, or the
    empty state. Bars are scaled to the busiest day; each is split into the
    correct part and the Again part, stacked."""
    if not s.total:
        return empty_html()
    peak = max(d.total for d in s.days)
    last = len(s.days) - 1
    cols = []
    for i, d in enumerate(s.days):
        today = i == last
        title = html.escape(day_title(d, today), quote=True)
        if d.total:
            h = max(6, round(100 * d.total / peak))
            segs = ""
            if d.again:
                segs += f'<i class="rf-dc-again" style="flex-grow:{d.again}"></i>'
            if d.correct:
                segs += f'<i class="rf-dc-good" style="flex-grow:{d.correct}"></i>'
            bar = f'<div class="rf-dc-bar" style="height:{h}%">{segs}</div>'
        else:
            bar = '<div class="rf-dc-stub"></div>'
        cls = "rf-dc-col rf-dc-today" if today else "rf-dc-col"
        # every other label on small widths is handled in CSS via rf-dc-alt
        alt = "" if (last - i) % 2 == 0 else " rf-dc-alt"
        cols.append(
            f'<div class="{cls}" title="{title}"><div class="rf-dc-plot">{bar}</div>'
            f'<span class="rf-dc-label{alt}">{day_label(d, today)}</span></div>'
        )
    aria = html.escape(aria_label(s), quote=True)
    return (
        f'<div class="rf-dc-chart" role="img" aria-label="{aria}">{"".join(cols)}</div>'
        f'<div class="rf-dc-foot"><span>{html.escape(summary_text(s))}</span>'
        '<span class="rf-dc-key"><i class="rf-dc-good"></i>Correct<i class="rf-dc-again"></i>Again</span></div>'
    )


def panel_html(deck_id: int, body: str | None) -> str:
    """The whole block placed under the counts card. Without `body` it holds a
    skeleton, and asks Python for the figures once the page has loaded (the
    page cannot be evaluated into before it exists)."""
    ask = ""
    if body is None:
        body = '<div class="rf-dc-skeleton"></div>'
        ask = (
            # pycmd is defined by Anki's web channel shortly after the DOM is
            # ready, so retry for a few seconds
            "<script>(function(){var n=0;function go(){if(typeof pycmd==='function')"
            f"{{pycmd('refine:overview:chart:{int(deck_id)}');return;}}"
            "if(n++<60)setTimeout(go,100);}go();})();</script>"
        )
    return (
        f'<section class="rf-dc rf-panel" id="rf-dc" data-did="{int(deck_id)}" aria-label="Last 14 days">'
        f'<h2 class="rf-dc-title">Last 14 days</h2><div class="rf-dc-body" id="rf-dc-body">{body}</div></section>'
        + ask
    )


def fill_js(deck_id: int, body: str) -> str:
    import json

    return (
        "(function(h){var e=document.getElementById('rf-dc');"
        f"if(!e||e.dataset.did!=='{int(deck_id)}')return;"
        "document.getElementById('rf-dc-body').innerHTML=h;})(" + json.dumps(body) + ");"
    )

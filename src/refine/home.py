"""Home-screen numbers and panel markup.

All figures are read-only queries over Anki's own data; nothing is stored.
"Today" follows Anki's own definition (rslib storage/revlog/studied_today.sql,
verified in M0): revlog.id > (day_cutoff - 86400) * 1000 and the entry is not
a Manual (4) or Rescheduled (5) one. The queries take a Collection and run in
a background QueryOp; the render functions are pure.
"""

from __future__ import annotations

import datetime
import html
import math
from dataclasses import dataclass, field
from typing import Any

DAY = 86400
ACTIVITY_DAYS = 182  # 26 weeks
STREAK_DAYS = 3 * 365
EXCLUDED_TYPES = "(4, 5)"


@dataclass
class Totals:
    new: int = 0
    learn: int = 0
    review: int = 0
    decks: int = 0

    @property
    def due(self) -> int:
        return self.new + self.learn + self.review


@dataclass
class HomeStats:
    today_cards: int = 0
    today_ms: int = 0
    activity: list[int] = field(default_factory=list)  # oldest .. today
    streak: int = 0
    best_streak: int = 0
    forecast: list[int] = field(default_factory=list)  # today .. +6
    avg_ms: float = 0.0


# --------------------------------------------------------------- queries


def totals(tree: Any) -> Totals:
    t = Totals()
    for node in getattr(tree, "children", []):
        t.new += node.new_count
        t.learn += node.learn_count
        t.review += node.review_count

    def count(n: Any) -> int:
        return 1 + sum(count(c) for c in n.children)

    t.decks = sum(count(c) for c in getattr(tree, "children", []))
    return t


def daily_counts(col: Any, days: int) -> list[int]:
    cutoff = col.sched.day_cutoff
    start = cutoff - days * DAY
    rows = col.db.all(
        f"select cast((id / 1000 - ?) / {DAY} as int) as d, count() from revlog "
        f"where id > ? and type not in {EXCLUDED_TYPES} group by d",
        start,
        start * 1000,
    )
    out = [0] * days
    for d, n in rows:
        if 0 <= d < days:
            out[d] = n
    return out


def streaks(counts: list[int]) -> tuple[int, int]:
    """(current, best). Current counts back from today, or from yesterday if
    nothing has been studied yet today (the day isn't over)."""
    best = run = 0
    for n in counts:
        run = run + 1 if n else 0
        best = max(best, run)
    cur = 0
    i = len(counts) - 1
    if i >= 0 and counts[i] == 0:
        i -= 1
    while i >= 0 and counts[i]:
        cur += 1
        i -= 1
    return cur, best


def forecast(col: Any, days: int = 7) -> list[int]:
    today = col.sched.today
    out = [0] * days
    for due, n in col.db.all(
        "select due, count() from cards where queue in (2, 3) and due < ? group by due",
        today + days,
    ):
        out[max(0, due - today)] += n
    out[0] += col.db.scalar("select count() from cards where queue = 1 and due < ?", col.sched.day_cutoff) or 0
    return out


def collect(col: Any) -> HomeStats:
    s = HomeStats()
    cutoff = col.sched.day_cutoff
    row = col.db.first(
        f"select count(), coalesce(sum(time), 0) from revlog where id > ? and type not in {EXCLUDED_TYPES}",
        (cutoff - DAY) * 1000,
    )
    s.today_cards, s.today_ms = int(row[0]), int(row[1])
    long = daily_counts(col, STREAK_DAYS)
    s.activity = long[-ACTIVITY_DAYS:]
    s.streak, s.best_streak = streaks(long)
    s.forecast = forecast(col)
    s.avg_ms = float(
        col.db.scalar(
            f"select coalesce(avg(time), 0) from revlog where id > ? and type not in {EXCLUDED_TYPES} and time > 0",
            (cutoff - 30 * DAY) * 1000,
        )
        or 0
    )
    return s


# --------------------------------------------------------------- markup


def fmt_int(n: int) -> str:
    return f"{n:,}"


def fmt_duration(ms: float) -> str:
    secs = int(round(ms / 1000))
    if secs < 60:
        return f"{secs}s"
    mins = int(round(secs / 60))
    if mins < 60:
        return f"{mins} min"
    h, m = divmod(mins, 60)
    return f"{h} h {m} min" if m else f"{h} h"


def hero_html(t: Totals, target_name: str | None, target_id: int | None, now: datetime.date | None = None) -> str:
    now = now or datetime.date.today()
    date = now.strftime("%A, %B ") + str(now.day)
    if t.due:
        title = f"{fmt_int(t.due)} card{'s' if t.due != 1 else ''} waiting"
    else:
        title = "All caught up"
    counts = (
        f'<span class="rf-stat"><b class="rf-c-new">{fmt_int(t.new)}</b> new</span>'
        f'<span class="rf-stat"><b class="rf-c-learn">{fmt_int(t.learn)}</b> learning</span>'
        f'<span class="rf-stat"><b class="rf-c-review">{fmt_int(t.review)}</b> due</span>'
        '<span class="rf-stat rf-faint" id="rf-pace"></span>'
    )
    button = ""
    if target_id is not None and t.due:
        name = html.escape(target_name or "")
        button = (
            f'<button class="rf-btn rf-btn-primary rf-btn-lg" title="Study {name}" '
            f"onclick=\"return pycmd('refine:deck_browser:study:{int(target_id)}')\">"
            f'Study <span class="rf-hero-deck">{name}</span></button>'
        )
    return (
        '<section class="rf-hero rf-panel" aria-label="Today\'s cards">'
        f'<div class="rf-hero-text"><div class="rf-muted rf-hero-date">{html.escape(date)}</div>'
        f'<h1 class="rf-hero-title">{title}</h1>'
        f'<div class="rf-hero-counts">{counts}</div></div>{button}</section>'
    )


def onboarding_html() -> str:
    """Shown instead of the headline when the collection has no cards yet.
    The buttons use the deck list's own commands (aqt/deckbrowser.py
    _linkHandler: create / import / shared)."""
    return (
        '<section class="rf-hero rf-panel rf-onboarding" aria-label="Get started">'
        '<div class="rf-hero-text"><div class="rf-muted rf-hero-date">Getting started</div>'
        '<h1 class="rf-hero-title">Welcome to Anki</h1>'
        '<p class="rf-muted rf-onboarding-text">Add your first cards with <b>Add</b>, or bring in a deck to study.</p>'
        "</div>"
        '<div class="rf-onboarding-actions">'
        "<button class=\"rf-btn rf-btn-primary rf-btn-lg\" onclick=\"return pycmd('create')\">Create a deck</button>"
        "<button class=\"rf-btn rf-btn-lg\" onclick=\"return pycmd('import')\">Import a file</button>"
        "<button class=\"rf-btn rf-btn-lg\" onclick=\"return pycmd('shared')\">Browse shared decks</button>"
        "</div></section>"
    )


def side_placeholder() -> str:
    def panel(cls: str, title: str) -> str:
        return (
            f'<section class="rf-panel rf-side-panel {cls}" aria-label="{title}">'
            f'<h2 class="rf-panel-title">{title}</h2><div class="rf-panel-body" data-rf-fill="{cls}">'
            '<div class="rf-skeleton"></div></div></section>'
        )

    return (
        '<aside class="rf-side">'
        + panel("rf-today", "Today")
        + panel("rf-activity", "Activity")
        + panel("rf-forecast", "Next 7 days")
        + "</aside>"
    )


def today_html(s: HomeStats, t: Totals) -> str:
    total = s.today_cards + t.due
    pct = 0 if total == 0 else round(100 * s.today_cards / total)
    tomorrow = s.forecast[1] if len(s.forecast) > 1 else 0
    if t.due == 0 and s.today_cards:
        note = "Done for today."
    elif t.due == 0:
        note = "Nothing due today."
    else:
        note = f"Clearing today’s cards leaves ≈ {fmt_int(tomorrow)} for tomorrow."
    return (
        f'<div class="rf-big"><span class="rf-big-num">{fmt_int(s.today_cards)}</span>'
        f'<span class="rf-muted">card{"s" if s.today_cards != 1 else ""} studied · {fmt_duration(s.today_ms)}</span></div>'
        f'<div class="rf-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{pct}">'
        f'<div style="width:{pct}%"></div></div>'
        f'<div class="rf-faint rf-small">{note}</div>'
    )


def activity_html(s: HomeStats) -> str:
    peak = max(s.activity) if s.activity else 0
    cells = []
    for n in s.activity:
        level = 0 if n == 0 or peak == 0 else min(4, max(1, math.ceil(4 * n / peak)))
        cells.append(f'<i class="rf-l{level}" title="{n} review{"s" if n != 1 else ""}"></i>')
    return (
        f'<div class="rf-heat" role="img" aria-label="Reviews per day, last 26 weeks">{"".join(cells)}</div>'
        f'<div class="rf-row rf-muted rf-small"><span>Streak {s.streak} day{"s" if s.streak != 1 else ""}</span>'
        f"<span>Best {s.best_streak}</span></div>"
    )


def forecast_html(s: HomeStats, today: datetime.date | None = None) -> str:
    today = today or datetime.date.today()
    peak = max(s.forecast) if s.forecast else 0
    bars = []
    for i, n in enumerate(s.forecast):
        # square-root scale: today's overdue backlog would otherwise flatten
        # every other day to nothing
        h = 4 if peak == 0 or n == 0 else max(8, round(100 * math.sqrt(n / peak)))
        label = (today + datetime.timedelta(days=i)).strftime("%a")[:2]
        cls = "rf-bar rf-bar-now" if i == 0 else "rf-bar"
        bars.append(
            f'<div class="rf-bar-col" title="{fmt_int(n)} due"><div class="{cls}" style="height:{h}%"></div>'
            f'<span class="rf-mono rf-faint">{label}</span></div>'
        )
    return f'<div class="rf-bars" role="img" aria-label="Cards due over the next 7 days">{"".join(bars)}</div>'


def pace_text(t: Totals, s: HomeStats) -> str:
    if not t.due or s.avg_ms <= 0:
        return ""
    return f"≈ {fmt_duration(t.due * s.avg_ms)} at your pace"

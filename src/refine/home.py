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
RETENTION_DAYS = 30
# below this many review answers a retention figure is noise, so show "—"
RETENTION_MIN_REVIEWS = 20


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
    # deck id -> (passed, total) review answers in the last RETENTION_DAYS,
    # for the deck itself only (parents are aggregated with the tree)
    retention: dict[int, tuple[int, int]] = field(default_factory=dict)
    today_passed: int = 0  # today's review answers that weren't "Again"
    today_reviews: int = 0
    # deck id -> (new cards not yet introduced, all cards), deck itself only
    progress: dict[int, tuple[int, int]] = field(default_factory=dict)
    # deck id -> cards whose note carries the "leech" tag, deck itself only
    leeches: dict[int, int] = field(default_factory=dict)
    # deck id -> options preset's new cards per day
    per_day: dict[int, int] = field(default_factory=dict)


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


def retention_by_deck(col: Any, days: int = RETENTION_DAYS) -> dict[int, tuple[int, int]]:
    """True retention inputs per deck, Anki's definition: review answers
    (revlog type 1) and how many of them weren't Again (ease > 1). Cards in
    a filtered deck count toward their home deck (odid)."""
    start = (col.sched.day_cutoff - days * DAY) * 1000
    out: dict[int, tuple[int, int]] = {}
    for did, odid, total, passed in col.db.all(
        "select c.did, c.odid, count(), sum(r.ease > 1) from revlog r "
        "join cards c on c.id = r.cid where r.id > ? and r.type = 1 group by c.did, c.odid",
        start,
    ):
        home = int(odid or did)
        p, t = out.get(home, (0, 0))
        out[home] = (p + int(passed or 0), t + int(total or 0))
    return out


def aggregate_retention(tree: Any, raw: dict[int, tuple[int, int]]) -> dict[int, int | None]:
    """Percent per deck including its subdecks; None when there are too few
    reviews for a meaningful figure."""
    out: dict[int, int | None] = {}

    def walk(node: Any) -> tuple[int, int]:
        p, t = raw.get(int(node.deck_id), (0, 0))
        for c in node.children:
            cp, ct = walk(c)
            p, t = p + cp, t + ct
        if int(node.deck_id):
            out[int(node.deck_id)] = round(100 * p / t) if t >= RETENTION_MIN_REVIEWS else None
        return p, t

    walk(tree)
    return out


def progress_by_deck(col: Any) -> dict[int, tuple[int, int]]:
    """(new cards left, total cards) per deck. "New left" counts cards of
    type 0 (never introduced), not queue 0: a buried new card (queue -2/-3)
    comes back tomorrow, so it is still left. A suspended new card
    (queue -1, e.g. a leech that was reset) can't be studied, so it is left
    out of both counts: a deck whose only unseen card is suspended shows no
    "new left" line instead of promising a card you can't study.
    Filtered-deck cards count toward their home deck (odid)."""
    out: dict[int, tuple[int, int]] = {}
    for did, odid, total, new in col.db.all(
        "select did, odid, count(), coalesce(sum(type = 0), 0) from cards "
        "where not (type = 0 and queue = -1) group by did, odid"
    ):
        home = int(odid or did)
        n, t = out.get(home, (0, 0))
        out[home] = (n + int(new or 0), t + int(total or 0))
    return out


def leeches_by_deck(col: Any) -> dict[int, int]:
    """Cards whose note is tagged "leech" per deck. Anki stores tags as
    " a b c " (space-padded) and LIKE is case-insensitive for ASCII, which is
    how Anki matches tags too. Hierarchical children (leech::x) are not
    counted."""
    out: dict[int, int] = {}
    for did, odid, n in col.db.all(
        "select c.did, c.odid, count() from cards c join notes n on n.id = c.nid "
        "where n.tags like '% leech %' group by c.did, c.odid"
    ):
        home = int(odid or did)
        out[home] = out.get(home, 0) + int(n or 0)
    return out


def per_day_by_deck(col: Any, deck_ids: Any) -> dict[int, int]:
    """New cards per day of each deck's options preset (filtered decks have
    no such setting and are skipped)."""
    out: dict[int, int] = {}
    for did in deck_ids:
        try:
            out[int(did)] = int(col.decks.config_dict_for_deck_id(int(did))["new"]["perDay"])
        except Exception:
            continue
    return out


def aggregate_sums(tree: Any, raw: dict[int, Any]) -> dict[int, tuple[int, ...]]:
    """Per deck, the element-wise sum of its own raw tuple (or int) and all
    its subdecks', like Anki's own list. Missing decks count as zeros."""
    out: dict[int, tuple[int, ...]] = {}

    def vec(v: Any) -> tuple[int, ...]:
        return tuple(v) if isinstance(v, (tuple, list)) else (int(v),)

    def walk(node: Any, width: int) -> tuple[int, ...]:
        own = vec(raw.get(int(node.deck_id), (0,) * width))
        for c in node.children:
            own = tuple(a + b for a, b in zip(own, walk(c, width)))
        if int(node.deck_id):
            out[int(node.deck_id)] = own
        return own

    sample = next(iter(raw.values()), 0)
    walk(tree, len(vec(sample)))
    return out


def leech_search(deck_name: str) -> str:
    """Browser search for a deck's leeches. Escapes \\ " * _ (wildcards) as
    Anki's search syntax requires; "deck:name" also matches subdecks."""
    quoted = deck_name.replace("\\", "\\\\").replace('"', '\\"').replace("*", "\\*").replace("_", "\\_")
    return f'"deck:{quoted}" tag:leech'


def eta_text(left: int, per_day: int) -> str:
    """"≈ 3 weeks to finish new cards at 20/day"; days under 14 days, weeks
    up to 16 weeks, months beyond. Empty when there is nothing to estimate."""
    if left <= 0 or per_day <= 0:
        return ""
    days = math.ceil(left / per_day)
    if days < 14:
        span = f"{days} day{'s' if days != 1 else ''}"
    elif days <= 16 * 7:
        w = round(days / 7)
        span = f"{w} weeks"
    else:
        m = round(days / 30)
        span = f"{m} months"
    return f"≈ {span} to finish new cards at {fmt_int(per_day)}/day"


def collect(col: Any) -> HomeStats:
    s = HomeStats()
    cutoff = col.sched.day_cutoff
    row = col.db.first(
        f"select count(), coalesce(sum(time), 0) from revlog where id > ? and type not in {EXCLUDED_TYPES}",
        (cutoff - DAY) * 1000,
    )
    s.today_cards, s.today_ms = int(row[0]), int(row[1])
    passed_total = col.db.first(
        "select coalesce(sum(ease > 1), 0), count() from revlog where id > ? and type = 1",
        (cutoff - DAY) * 1000,
    )
    s.today_passed, s.today_reviews = int(passed_total[0]), int(passed_total[1])
    s.retention = retention_by_deck(col)
    s.progress = progress_by_deck(col)
    s.leeches = leeches_by_deck(col)
    s.per_day = per_day_by_deck(col, s.progress)
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


def hero_title(due: int) -> str:
    return f"{fmt_int(due)} card{'s' if due != 1 else ''} waiting" if due else "All caught up"


def hero_html(
    t: Totals,
    deck_name: str | None,
    deck_id: int | None,
    now: datetime.date | None = None,
) -> str:
    """The headline. With a deck selected it shows that deck's numbers and a
    Study button; with none selected, all decks combined. refine.js updates
    the same elements in place when the selection changes (no reload)."""
    now = now or datetime.date.today()
    date = now.strftime("%A, %B ") + str(now.day)
    scope = html.escape(deck_name) if deck_name else "All decks"
    counts = (
        f'<span class="rf-stat"><b class="rf-c-new" data-rf="new">{fmt_int(t.new)}</b> new</span>'
        f'<span class="rf-stat"><b class="rf-c-learn" data-rf="learn">{fmt_int(t.learn)}</b> learning</span>'
        f'<span class="rf-stat"><b class="rf-c-review" data-rf="review">{fmt_int(t.review)}</b> due</span>'
        '<span class="rf-stat rf-faint" id="rf-pace"></span>'
        '<span class="rf-stat rf-faint" id="rf-eta"></span>'
    )
    return (
        '<section class="rf-hero rf-panel" aria-label="Cards waiting" aria-live="polite">'
        '<div class="rf-hero-text">'
        f'<div class="rf-muted rf-hero-date"><span class="rf-hero-scope">{scope}</span>'
        f' · {html.escape(date)}</div>'
        f'<h1 class="rf-hero-title">{hero_title(t.due)}</h1>'
        f'<div class="rf-hero-counts">{counts}</div></div>'
        f'<div class="rf-hero-action">{hero_action(deck_name, deck_id, t.due)}</div>'
        "</section>"
    )


def hero_action(deck_name: str | None, deck_id: int | None, due: int) -> str:
    if deck_id is None:
        return '<span class="rf-hero-hint rf-muted">Choose a deck below to study it</span>'
    name = html.escape(deck_name or "")
    if not due:
        return f'<span class="rf-hero-hint rf-muted">Nothing due in {name}</span>'
    return (
        f'<button class="rf-btn rf-btn-primary rf-btn-lg" title="Study {name}" '
        f"onclick=\"return pycmd('refine:deck_browser:study:{int(deck_id)}')\">"
        f'Study <span class="rf-hero-deck">{name}</span></button>'
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


def side_placeholder(filled: dict | None = None) -> str:
    """Side panels. With `filled` (panel class -> html from the last query)
    they render complete at once instead of as placeholders."""
    filled = filled or {}

    def panel(cls: str, title: str) -> str:
        body = filled.get(cls) or '<div class="rf-skeleton"></div>'
        return (
            f'<section class="rf-panel rf-side-panel {cls}" aria-label="{title}">'
            f'<h2 class="rf-panel-title">{title}</h2><div class="rf-panel-body" data-rf-fill="{cls}">'
            f"{body}</div></section>"
        )

    return (
        '<aside class="rf-side">'
        + panel("rf-today", "Today")
        + panel("rf-activity", "Activity")
        + panel("rf-forecast", "Next 7 days")
        + "</aside>"
    )


def today_html(s: HomeStats, t: Totals, goal: int = 0) -> str:
    tomorrow = s.forecast[1] if len(s.forecast) > 1 else 0
    if goal > 0:
        # progress towards the user's daily goal
        pct = min(100, round(100 * s.today_cards / goal))
        left = goal - s.today_cards
        note = (
            f"Goal of {fmt_int(goal)} reached." if left <= 0
            else f"{fmt_int(left)} more to reach today’s goal of {fmt_int(goal)}."
        )
    else:
        # progress through what is due today
        total = s.today_cards + t.due
        pct = 0 if total == 0 else round(100 * s.today_cards / total)
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


def _day_label(day: datetime.date, offset: int) -> str:
    """"Today", "Yesterday"/"Tomorrow", else "Mon, Oct 20" (hover tips)."""
    if offset == 0:
        return "Today"
    if offset in (-1, 1):
        return "Yesterday" if offset < 0 else "Tomorrow"
    return f"{day:%a}, {day:%b} {day.day}"


def activity_html(s: HomeStats, today: datetime.date | None = None) -> str:
    today = today or datetime.date.today()
    peak = max(s.activity) if s.activity else 0
    last = len(s.activity) - 1
    cells = []
    for i, n in enumerate(s.activity):
        level = 0 if n == 0 or peak == 0 else min(4, max(1, math.ceil(4 * n / peak)))
        day = today - datetime.timedelta(days=last - i)
        tip = f'{_day_label(day, i - last)} · {fmt_int(n)} review{"s" if n != 1 else ""}'
        cells.append(f'<i class="rf-l{level}" data-rf-tip="{tip}"></i>')
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
        day = today + datetime.timedelta(days=i)
        label = day.strftime("%a")[:2]
        cls = "rf-bar rf-bar-now" if i == 0 else "rf-bar"
        tip = f"{_day_label(day, i)} · {fmt_int(n)} due"
        bars.append(
            f'<div class="rf-bar-col" data-rf-tip="{tip}"><div class="{cls}" style="height:{h}%"></div>'
            f'<span class="rf-mono rf-faint">{label}</span></div>'
        )
    return f'<div class="rf-bars" role="img" aria-label="Cards due over the next 7 days">{"".join(bars)}</div>'


def session_summary_html(s: HomeStats) -> str:
    """One calm sentence for the "finished this deck" screen, from Anki's
    own review log; no badges, no fireworks."""
    if not s.today_cards:
        return ""
    parts = [f"<b>{fmt_int(s.today_cards)}</b> card{'s' if s.today_cards != 1 else ''} in <b>{fmt_duration(s.today_ms)}</b>"]
    if s.today_reviews >= 5:
        parts.append(f"<b>{round(100 * s.today_passed / s.today_reviews)}%</b> of reviews correct")
    sentence = "Today: " + ", ".join(parts) + "."
    extra = []
    if len(s.forecast) > 1:
        tomorrow = s.forecast[1]
        extra.append(f"Tomorrow ≈ <b>{fmt_int(tomorrow)}</b> due" if tomorrow else "Nothing due tomorrow")
    if s.streak > 1:
        extra.append(f"<b>{s.streak}</b>-day streak")
    if extra:
        sentence += " " + " · ".join(extra) + "."
    return f'<section class="rf-session" aria-label="Today’s session"><p>{sentence}</p></section>'


def pace_text(t: Totals, s: HomeStats) -> str:
    if not t.due or s.avg_ms <= 0:
        return ""
    return f"≈ {fmt_duration(t.due * s.avg_ms)} at your pace"

"""Home screen: restyled deck list plus the hero and side panels.

Anki's own markup is left in place (other add-ons and Anki's drag-and-drop
rely on it); Refine appends its panels to DeckBrowserContent.stats and lays
the page out with CSS grid. Panel data is fetched in a background QueryOp
after render and filled in by refine.js.
"""

from __future__ import annotations

import json
import time
from typing import Any

from aqt import gui_hooks

from .. import home
from .base import WebSurface


class DeckBrowserSurface(WebSurface):
    id = "deck_browser"
    requires_hooks = (
        "deck_browser_will_render_content",
        "deck_browser_did_render",
        "deck_browser_will_show_options_menu",
    )
    contexts = ("DeckBrowser", "DeckBrowserBottomBar")
    css = ("deck-browser.css",)

    def __init__(self) -> None:
        self._totals = home.Totals()
        self._generation = 0
        # last panel markup and the collection state it was computed for, so
        # Home renders complete at once and only re-queries after changes
        self._panels: dict[str, str] = {}
        self._panels_key: tuple | None = None
        self._render_key: tuple | None = None
        # the deck selected on Home (None = all decks); Refine-only state, so
        # "nothing selected" is possible even though Anki always has a current deck
        self._selected: int | None = None
        self._avg_ms = 0.0
        self._retention_raw: dict = {}  # deck id -> (passed, total), last query
        self._progress_raw: dict = {}  # deck id -> (new left, total), last query
        self._leech_raw: dict = {}  # deck id -> leech cards, last query
        self._per_day: dict = {}  # deck id -> new cards per day
        self._tree = None

    def flags(self, cfg: dict) -> dict[str, bool]:
        h = cfg.get("home", {})
        out = {f"rf-h-{k}": bool(v) for k, v in h.items()}
        # read by refine.js at click time, so the setting applies live
        out["rf-click-select"] = cfg.get("deck_click", "select") == "select"
        return out

    def install(self, ctx: Any) -> None:
        self._will = ctx.guard.wrap(self.id, lambda db, content: self._will_render(ctx, db, content))
        self._did = ctx.guard.wrap(self.id, lambda db: self._did_render(ctx, db))
        gui_hooks.deck_browser_will_render_content.append(self._will)
        gui_hooks.deck_browser_did_render.append(self._did)
        self._menu = ctx.guard.wrap(self.id, lambda menu, did: self._options_menu(ctx, menu, did))
        gui_hooks.deck_browser_will_show_options_menu.append(self._menu)

    def uninstall(self, ctx: Any) -> None:
        gui_hooks.deck_browser_will_render_content.remove(self._will)
        gui_hooks.deck_browser_did_render.remove(self._did)
        gui_hooks.deck_browser_will_show_options_menu.remove(self._menu)

    def _active(self, ctx: Any) -> bool:
        cfg = ctx.config.get()
        return bool(cfg.get("enabled") and cfg["surfaces"].get(self.id))

    # ---------------------------------------------------------------- render

    def _will_render(self, ctx: Any, deck_browser: Any, content: Any) -> None:
        if not ctx.config.get().get("enabled"):
            return
        tree = getattr(getattr(deck_browser, "_render_data", None), "tree", None)
        if tree is None:
            tree = ctx.mw.col.sched.deck_due_tree()
        self._totals = home.totals(tree)
        self._tree = tree
        decks = self._deck_counts(tree)
        if self._selected not in decks:
            self._selected = None  # deck deleted or filtered away
        # panels are always emitted when Refine is on; CSS shows them only
        # under html.rf-s-deck_browser.rf-h-*, so toggles apply live
        if ctx.mw.col.card_count() == 0:
            # a new collection: a welcome with next steps, not "All caught up"
            hero = home.onboarding_html()
        else:
            sel = decks.get(self._selected) if self._selected is not None else None
            if sel:
                t = home.Totals(new=sel["new"], learn=sel["learn"], review=sel["review"])
                hero = home.hero_html(t, sel["name"], self._selected)
            else:
                t = self._totals
                hero = home.hero_html(t, None, None)
            pace = home.pace_text(t, home.HomeStats(avg_ms=self._avg_ms))
            if pace:
                import html as _html

                hero = hero.replace('id="rf-pace"></span>', f'id="rf-pace">{_html.escape(pace)}</span>', 1)
        self._render_key = self._key(ctx)
        data = {
            "decks": {str(k): v for k, v in decks.items()},
            "all": {"new": self._totals.new, "learn": self._totals.learn, "review": self._totals.review},
            "selected": self._selected,
            "avgMs": self._avg_ms,
            "retention": self._retention_pct(),
            "progress": self._progress(),
            "leeches": self._leeches(),
        }
        # data for refine.js, which switches the headline in place on click
        blob = json.dumps(data).replace("</", "<\\/")
        content.stats = (
            hero
            + f'<script type="application/json" id="rf-deck-data">{blob}</script>'
            + home.side_placeholder(self._panels)
            + content.stats
        )

    def _retention_pct(self) -> dict[str, int | None]:
        if self._tree is None or not self._retention_raw:
            return {}
        agg = home.aggregate_retention(self._tree, self._retention_raw)
        return {str(k): v for k, v in agg.items()}

    def _progress(self) -> dict[str, dict]:
        if self._tree is None or not self._progress_raw:
            return {}
        agg = home.aggregate_sums(self._tree, self._progress_raw)
        return {
            str(k): {"left": v[0], "total": v[1], "perDay": self._per_day.get(k, 0)}
            for k, v in agg.items()
            if v[0] > 0
        }

    def _leeches(self) -> dict[str, int]:
        if self._tree is None or not self._leech_raw:
            return {}
        agg = home.aggregate_sums(self._tree, self._leech_raw)
        return {str(k): v[0] for k, v in agg.items() if v[0] > 0}

    @staticmethod
    def _deck_counts(tree: Any) -> dict[int, dict]:
        """deck id -> its name (as shown in the list) and due counts, which
        include subdecks, as in Anki's own list."""
        out: dict[int, dict] = {}

        def walk(node: Any) -> None:
            for c in node.children:
                out[int(c.deck_id)] = {
                    "name": c.name,
                    "new": c.new_count,
                    "learn": c.learn_count,
                    "review": c.review_count,
                }
                walk(c)

        walk(tree)
        return out

    def _key(self, ctx: Any) -> tuple:
        """Changes whenever the panel figures could: any collection change,
        a new day, or a different daily goal."""
        col = ctx.mw.col
        return (col.mod, col.sched.today, ctx.config.get().get("daily_goal", 0))

    def _did_render(self, ctx: Any, deck_browser: Any) -> None:
        if not ctx.config.get().get("enabled"):
            return
        from aqt.operations import QueryOp

        if self._panels and self._render_key == self._panels_key:
            return  # the page already shows up-to-date panels
        self._generation += 1
        gen = self._generation
        totals = self._totals
        key = self._render_key

        def done(stats: home.HomeStats) -> None:
            if gen != self._generation or ctx.mw.state != "deckBrowser":
                return  # a newer render superseded this one
            payload = {
                "rf-today": home.today_html(stats, totals, int(ctx.config.get().get("daily_goal", 0))),
                "rf-activity": home.activity_html(stats),
                "rf-forecast": home.forecast_html(stats),
            }
            changed = {k: v for k, v in payload.items() if self._panels.get(k) != v}
            if stats.avg_ms != self._avg_ms:
                changed["avgMs"] = stats.avg_ms
            if stats.retention != self._retention_raw:
                self._retention_raw = stats.retention
                changed["retention"] = self._retention_pct()
            if stats.progress != self._progress_raw or stats.per_day != self._per_day:
                self._progress_raw, self._per_day = stats.progress, stats.per_day
                changed["progress"] = self._progress()
            if stats.leeches != self._leech_raw:
                self._leech_raw = stats.leeches
                changed["leeches"] = self._leeches()
            self._panels, self._panels_key, self._avg_ms = payload, key, stats.avg_ms
            if changed:  # only touch the page if something differs
                ctx.mw.web.eval(f"window.rfFillHome && window.rfFillHome({json.dumps(changed)});")

        def failed(err: Exception) -> None:
            ctx.log.error("home stats failed: %r", err)

        def timed(col: Any) -> home.HomeStats:
            t0 = time.perf_counter()
            stats = home.collect(col)
            ctx.log.info("home stats in %.1f ms", (time.perf_counter() - t0) * 1000)
            return stats

        QueryOp(parent=ctx.mw, op=timed, success=ctx.guard.wrap(self.id, done)).failure(
            failed
        ).run_in_background()

    # ---------------------------------------------------------------- bridge

    def on_bridge(self, ctx: Any, cmd: str, context: Any) -> None:
        verb, _, arg = cmd.partition(":")
        if verb == "study" and arg.isdigit():
            self._study(ctx, int(arg))
        elif verb == "select" and arg.isdigit():
            self._selected = int(arg)
            self._select(ctx, int(arg))
        elif verb == "deselect":
            self._selected = None
        elif verb == "leeches" and arg.isdigit():
            self._show_leeches(ctx, int(arg))

    def _show_leeches(self, ctx: Any, deck_id: int) -> None:
        """Open the Browser on this deck's (and subdecks') leech cards."""
        import aqt

        mw = ctx.mw
        name = mw.col.decks.name(deck_id)
        browser = aqt.dialogs.open("Browser", mw)
        browser.search_for(home.leech_search(name))

    def _select(self, ctx: Any, deck_id: int) -> None:
        """Make a deck current and stay on Home. Same operation as Anki's
        Shift-click on a row."""
        from aqt.operations.deck import set_current_deck

        # The page already updated itself (refine.js). initiator=deckBrowser
        # makes Anki skip its reload, exactly as for its own Shift-click.
        mw = ctx.mw
        set_current_deck(parent=mw, deck_id=deck_id).run_in_background(initiator=mw.deckBrowser)

    def _options_menu(self, ctx: Any, menu: Any, deck_id: int) -> None:
        """Adds "Open overview" to a deck's ⋯ menu, since a click on the deck
        name now stays on Home."""
        if not ctx.config.get().get("enabled"):
            return
        menu.addSeparator()
        action = menu.addAction("Open overview")
        action.triggered.connect(ctx.guard.wrap(self.id, lambda *_: ctx.mw.deckBrowser.set_current_deck(deck_id)))

    def _study(self, ctx: Any, deck_id: int) -> None:
        # same steps as the overview's "Study Now" (aqt/overview.py _linkHandler)
        from aqt.operations.deck import set_current_deck

        mw = ctx.mw

        def start(_: Any) -> None:
            mw.col.startTimebox()
            mw.moveToState("review")
            if mw.state != "review":
                mw.moveToState("overview")

        set_current_deck(parent=mw, deck_id=deck_id).success(start).run_in_background()

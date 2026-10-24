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
        target_id, target_name = self._study_target(ctx, tree)
        # panels are always emitted when Refine is on; CSS shows them only
        # under html.rf-s-deck_browser.rf-h-*, so toggles apply live
        if ctx.mw.col.card_count() == 0:
            # a new collection: a welcome with next steps, not "All caught up"
            hero = home.onboarding_html()
        else:
            hero = home.hero_html(self._totals, target_name, target_id)
        content.stats = hero + home.side_placeholder() + content.stats

    def _study_target(self, ctx: Any, tree: Any) -> tuple[int | None, str | None]:
        """The current deck if it has cards waiting, else the first top-level
        deck that does. Anki has no "study everything" queue, so the hero
        button is explicit about which deck it opens."""
        col = ctx.mw.col
        current = col.decks.get_current_id()

        def find(node: Any) -> Any:
            if node.deck_id == current:
                return node
            for c in node.children:
                hit = find(c)
                if hit is not None:
                    return hit
            return None

        node = find(tree)
        if node is not None and (node.new_count + node.learn_count + node.review_count):
            return node.deck_id, col.decks.name(node.deck_id)
        for c in tree.children:
            if c.new_count + c.learn_count + c.review_count:
                return c.deck_id, c.name
        return None, None

    def _did_render(self, ctx: Any, deck_browser: Any) -> None:
        if not ctx.config.get().get("enabled"):
            return
        from aqt.operations import QueryOp

        self._generation += 1
        gen = self._generation
        totals = self._totals

        def done(stats: home.HomeStats) -> None:
            if gen != self._generation or ctx.mw.state != "deckBrowser":
                return  # a newer render superseded this one
            payload = {
                "rf-today": home.today_html(stats, totals, int(ctx.config.get().get("daily_goal", 0))),
                "rf-activity": home.activity_html(stats),
                "rf-forecast": home.forecast_html(stats),
                "pace": home.pace_text(totals, stats),
            }
            ctx.mw.web.eval(f"window.rfFillHome && window.rfFillHome({json.dumps(payload)});")

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
            self._select(ctx, int(arg))

    def _select(self, ctx: Any, deck_id: int) -> None:
        """Make a deck current and stay on Home (the headline's Study button
        follows it). Same operation as Anki's Shift-click on a row."""
        from aqt.operations.deck import set_current_deck

        mw = ctx.mw
        set_current_deck(parent=mw, deck_id=deck_id).success(
            lambda _: mw.deckBrowser.refresh() if mw.state == "deckBrowser" else None
        ).run_in_background()

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

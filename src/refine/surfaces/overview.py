"""Deck overview (the screen with "Study Now"), plus the "finished this deck"
congrats page that Anki shows in its place.

The congrats page is a SvelteKit page loaded by URL, so it never passes
through webview_will_set_content. Anki fires webview_did_inject_style_into_page
once it has loaded (M0 report); Refine then adds its tokens and a small
stylesheet that targets plain elements only (the page's own class names are
hashed build output and change between releases).
"""

from __future__ import annotations

from typing import Any

from aqt import gui_hooks

from .base import WebSurface
from .pages import inject_page


class OverviewSurface(WebSurface):
    id = "overview"
    requires_hooks = (
        "webview_will_set_content",
        "webview_did_inject_style_into_page",
        "overview_will_render_content",
    )
    contexts = ("Overview", "OverviewBottomBar")
    css = ("overview.css",)

    def __init__(self) -> None:
        # (deck id, col.mod, sched.today) -> chart body, so a revisit paints at once
        self._cache: dict[tuple, str] = {}

    def flags(self, cfg: dict) -> dict[str, bool]:
        return {"rf-overview-chart": bool(cfg.get("overview_chart", True))}

    def install(self, ctx: Any) -> None:
        self._hook = ctx.guard.wrap(self.id, lambda web: self._on_page(ctx, web))
        gui_hooks.webview_did_inject_style_into_page.append(self._hook)
        self._will = ctx.guard.wrap(self.id, lambda ov, content: self._will_render(ctx, content))
        gui_hooks.overview_will_render_content.append(self._will)

    def uninstall(self, ctx: Any) -> None:
        gui_hooks.webview_did_inject_style_into_page.remove(self._hook)
        gui_hooks.overview_will_render_content.remove(self._will)

    def on_config(self, ctx: Any, cfg: dict, changed: frozenset) -> None:
        if "overview_chart" in changed and getattr(ctx.mw, "state", "") == "overview":
            ctx.mw.overview.refresh()  # the panel is only in the markup when on

    # ------------------------------------------------------------ chart

    def _key(self, ctx: Any, deck_id: int) -> tuple:
        col = ctx.mw.col
        return (deck_id, col.mod, col.sched.today)

    def _will_render(self, ctx: Any, content: Any) -> None:
        cfg = ctx.config.get()
        if not (cfg.get("enabled") and cfg["surfaces"].get(self.id) and cfg.get("overview_chart", True)):
            return
        from .. import deck_stats

        did = int(ctx.mw.col.decks.get_current_id())
        body = self._cache.get(self._key(ctx, did))
        content.table += deck_stats.panel_html(did, body)

    def on_bridge(self, ctx: Any, cmd: str, context: Any) -> None:
        verb, _, arg = cmd.partition(":")
        if verb == "chart" and arg.isdigit():
            self._query(ctx, int(arg))

    def _query(self, ctx: Any, did: int) -> None:
        from aqt.operations import QueryOp

        from .. import deck_stats

        key = self._key(ctx, did)

        def done(series: Any) -> None:
            body = deck_stats.chart_html(series)
            if len(self._cache) > 32:
                self._cache.clear()
            self._cache[key] = body
            if ctx.mw.state == "overview" and ctx.mw.col.decks.get_current_id() == did:
                ctx.mw.web.eval(deck_stats.fill_js(did, body))

        QueryOp(
            parent=ctx.mw, op=lambda col: deck_stats.collect(col, did), success=ctx.guard.wrap(self.id, done)
        ).failure(lambda err: ctx.log.error("deck chart failed: %r", err)).run_in_background()

    def _on_page(self, ctx: Any, web: Any) -> None:
        url = web.url().toString()
        if web is not getattr(ctx.mw, "web", None):
            return
        if "congrats" not in url:
            return
        cfg = ctx.config.get()
        if not (cfg.get("enabled") and cfg["surfaces"].get(self.id)):
            return
        inject_page(ctx, web, self.id, "congrats", ("congrats.css",))
        self._session_summary(ctx, web)

    def _session_summary(self, ctx: Any, web: Any) -> None:
        """Today's session in one sentence under Anki's congratulations,
        computed off the main thread from Anki's review log."""
        import json

        from aqt.operations import QueryOp

        from .. import home

        def show(stats: Any) -> None:
            markup = home.session_summary_html(stats)
            if markup and "congrats" in web.url().toString():
                web.eval(
                    "(function(h){if(document.querySelector('.rf-session'))return;"
                    f"document.body.insertAdjacentHTML('beforeend',h);}})({json.dumps(markup)});"
                )

        QueryOp(parent=ctx.mw, op=home.collect, success=ctx.guard.wrap(self.id, show)).failure(
            lambda err: ctx.log.error("session summary failed: %r", err)
        ).run_in_background()

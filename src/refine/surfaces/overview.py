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
    requires_hooks = ("webview_will_set_content", "webview_did_inject_style_into_page")
    contexts = ("Overview", "OverviewBottomBar")
    css = ("overview.css",)

    def install(self, ctx: Any) -> None:
        self._hook = ctx.guard.wrap(self.id, lambda web: self._on_page(ctx, web))
        gui_hooks.webview_did_inject_style_into_page.append(self._hook)

    def uninstall(self, ctx: Any) -> None:
        gui_hooks.webview_did_inject_style_into_page.remove(self._hook)

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

"""Deck overview (the screen with "Study Now"), plus the "finished this deck"
congrats page that Anki shows in its place.

The congrats page is a SvelteKit page loaded by URL, so it never passes
through webview_will_set_content. Anki fires webview_did_inject_style_into_page
once it has loaded (M0 report); Refine then adds its tokens and a small
stylesheet that targets plain elements only (the page's own class names are
hashed build output and change between releases).
"""

from __future__ import annotations

import json
from typing import Any

from aqt import gui_hooks

from ..theme import css as theme_css
from .base import WebSurface


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
        base = ctx.web_base
        payload = {
            "classes": ["refine", f"rf-s-{self.id}", "rf-page-congrats"],
            "links": [f"{base}/css/fonts.css", f"{base}/css/congrats.css"],
            "script": f"{base}/js/refine.js",
            "tokens": theme_css.root_css(cfg["accent"], cfg["density"]),
            "styleId": theme_css.STYLE_ID,
        }
        # The page resets <html>'s class list after it loads, so a
        # MutationObserver keeps Refine's classes (window.rfKeep, which
        # refine.js's rfApply updates on live settings changes) in place.
        web.eval(
            "(function(p){var d=document.documentElement;"
            "window.rfKeep=p.classes.slice();"
            "var keep=function(){window.rfKeep.forEach(function(c){"
            "if(!d.classList.contains(c)) d.classList.add(c);});};"
            "keep();new MutationObserver(keep).observe(d,{attributes:true,attributeFilter:['class']});"
            "p.links.forEach(function(h){var l=document.createElement('link');"
            "l.rel='stylesheet';l.href=h;document.head.appendChild(l);});"
            "var s=document.createElement('style');s.id=p.styleId;s.textContent=p.tokens;"
            "document.head.appendChild(s);"
            "var j=document.createElement('script');j.src=p.script;document.head.appendChild(j);"
            f"}})({json.dumps(payload)});"
        )

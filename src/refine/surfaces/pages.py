"""Anki's SvelteKit pages (Statistics, Deck Options, the congrats screen).

These load by URL, so they never pass through webview_will_set_content;
Anki fires webview_did_inject_style_into_page once one has loaded. They are
built on Anki's own CSS variables (--canvas, --fg, --border, ...), so
Refine's token block, which remaps those variables, restyles most of a page
without touching its markup. Extra rules target plain elements only: the
pages' class names are hashed build output.
"""

from __future__ import annotations

import json
from typing import Any

from aqt import gui_hooks

from ..theme import css as theme_css
from .base import Surface


def inject_page(ctx: Any, web: Any, surface_id: str, page: str, css_files: tuple[str, ...]) -> None:
    """Add Refine's classes, tokens, fonts and css to an already-loaded page.

    SvelteKit pages reset <html>'s class list after load, so a
    MutationObserver keeps Refine's classes (window.rfKeep; refine.js's
    rfApply updates it when settings change live)."""
    cfg = ctx.config.get()
    base = ctx.web_base
    payload = {
        "classes": ["refine", f"rf-s-{surface_id}", f"rf-page-{page}"],
        "links": [f"{base}/css/fonts.css"] + [f"{base}/css/{f}" for f in css_files],
        "script": f"{base}/js/refine.js",
        "tokens": theme_css.root_css(cfg["accent"], cfg["density"]),
        "styleId": theme_css.STYLE_ID,
    }
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


def _kind_name(web: Any) -> str:
    kind = getattr(web, "kind", None)
    return getattr(kind, "name", "") if kind is not None else ""


class PagesSurface(Surface):
    """Statistics and Deck Options windows."""

    id = "pages"
    requires_hooks = ("webview_did_inject_style_into_page",)
    # AnkiWebViewKind names -> page id used in CSS (html.rf-page-<id>).
    # The editor and image-occlusion pages show user content under a strict
    # CSP and are deliberately excluded.
    KINDS = {"DECK_STATS": "stats", "DECK_OPTIONS": "deck-options"}

    def install(self, ctx: Any) -> None:
        self._hook = ctx.guard.wrap(self.id, lambda web: self._on_page(ctx, web))
        gui_hooks.webview_did_inject_style_into_page.append(self._hook)

    def uninstall(self, ctx: Any) -> None:
        gui_hooks.webview_did_inject_style_into_page.remove(self._hook)

    def _on_page(self, ctx: Any, web: Any) -> None:
        page = self.KINDS.get(_kind_name(web))
        if page is None:
            return
        cfg = ctx.config.get()
        if not (cfg.get("enabled") and cfg["surfaces"].get(self.id)):
            return
        inject_page(ctx, web, self.id, page, ("pages.css",))

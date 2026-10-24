"""Reviewer bottom bar: Show Answer, Again/Hard/Good/Easy, Edit, More.

Only the bottom-bar webview is touched. The card webview (context
"Reviewer") is deliberately not matched, so card templates render exactly as
in stock Anki.
"""

from __future__ import annotations

from typing import Any

from .base import WebSurface


def canvas_css(selector: str) -> str:
    """Background rule using Anki's own window canvas, so Refine's bars blend
    with the card area (whose default background is that canvas)."""
    try:
        from aqt import colors

        light, dark = colors.CANVAS["light"], colors.CANVAS["dark"]
    except Exception:
        light, dark = "#f5f5f5", "#2c2c2c"
    return (
        f"<style>html.refine{selector} body{{background:{light}}}"
        f"html.refine.night-mode{selector} body{{background:{dark}}}</style>"
    )


class ReviewerSurface(WebSurface):
    id = "reviewer"
    requires_hooks = ("webview_will_set_content",)
    contexts = ("ReviewerBottomBar",)
    css = ("reviewer-bottom.css",)

    def flags(self, cfg: dict) -> dict[str, bool]:
        return {"rf-ease-colors": bool(cfg.get("reviewer", {}).get("ease_colors", True))}

    def contribute(self, ctx: Any, web_content: Any, context: Any, cfg: dict) -> None:
        web_content.head += canvas_css(".rf-s-reviewer")

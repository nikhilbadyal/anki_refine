"""Deck overview (the screen with "Study Now")."""

from __future__ import annotations

from .base import WebSurface


class OverviewSurface(WebSurface):
    id = "overview"
    requires_hooks = ("webview_will_set_content",)
    contexts = ("Overview", "OverviewBottomBar")
    css = ("overview.css",)

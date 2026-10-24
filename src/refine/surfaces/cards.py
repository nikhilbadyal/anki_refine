"""Opt-in card-content layer: Japanese reading polish.

This is the only part of Refine that touches card rendering, so it is off
by default and deliberately minimal:
- every rule is zero-specificity (:where), so any card-template rule wins;
- the card webviews get no Refine tokens, fonts or html.refine class (those
  remap Anki's --canvas and would change card backgrounds);
- it only adds two html classes, rf-cards-ja and rf-furigana-hover.
"""

from __future__ import annotations

from .base import WebSurface


class CardsSurface(WebSurface):
    id = "cards"
    requires_hooks = ("webview_will_set_content",)
    contexts = ("Reviewer", "BrowserPreviewer", "CardLayout")
    css = ("cards.css",)
    scope = "cards"  # restricted: see Registry._on_set_content

    def flags(self, cfg: dict) -> dict[str, bool]:
        c = cfg.get("cards", {})
        ja = bool(c.get("japanese"))
        return {
            "rf-cards-ja": ja,
            "rf-furigana-hover": ja and bool(c.get("furigana_hover")),
        }

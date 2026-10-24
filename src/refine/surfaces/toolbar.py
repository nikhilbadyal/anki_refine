"""Top toolbar (Decks / Add / Browse / Stats / Sync) and the shared bottom bars."""

from __future__ import annotations

import json
from typing import Any

from aqt import gui_hooks

from .base import WebSurface


class ToolbarSurface(WebSurface):
    id = "toolbar"
    requires_hooks = ("webview_will_set_content", "state_did_change")
    contexts = ("TopToolbar",)
    css = ("toolbar.css",)

    def contribute(self, ctx: Any, web_content: Any, context: Any, cfg: dict) -> None:
        from .reviewer import canvas_css

        # while reviewing, the toolbar sits on the card canvas like stock Anki
        web_content.head += canvas_css('.rf-s-toolbar[data-rf-state="review"]')

    def install(self, ctx: Any) -> None:
        self._hook = ctx.guard.wrap(self.id, lambda new, old: self._on_state(ctx, new))
        gui_hooks.state_did_change.append(self._hook)

    def uninstall(self, ctx: Any) -> None:
        gui_hooks.state_did_change.remove(self._hook)

    def _on_state(self, ctx: Any, state: str) -> None:
        # highlights the current screen's link without re-rendering the toolbar
        web = getattr(ctx.mw, "toolbarWeb", None)
        if web is not None:
            web.eval(f"window.rfSetState && window.rfSetState({json.dumps(state)});")
            # the review state is more compact; re-measure like Anki does when
            # its own body classes change (evals run in order)
            # (skipped when Anki's "hide top bar" mode animates the height itself)
            hide_mode = getattr(ctx.mw.pm, "hide_top_bar", lambda: False)()
            if hasattr(web, "adjustHeightToFit") and not hide_mode:
                web.adjustHeightToFit()

"""Qt widgets: menus, tooltips, scrollbars, focus rings.

Anki applies its stylesheet before add-ons load, so style_did_init misses the
first application (M0 report F2). We therefore splice our marked block into
the app stylesheet ourselves at install time, and let the filter re-add it on
every later theme change.
"""

from __future__ import annotations

from typing import Any

from aqt import gui_hooks

from ..theme import qss, tokens
from .base import Surface


class QtChromeSurface(Surface):
    id = "qt_chrome"
    requires_hooks = ("style_did_init",)

    def install(self, ctx: Any) -> None:
        self._filter = ctx.guard.wrap(self.id, lambda buf: self._on_style(ctx, buf), is_filter=True)
        gui_hooks.style_did_init.append(self._filter)
        self.apply(ctx)

    def uninstall(self, ctx: Any) -> None:
        gui_hooks.style_did_init.remove(self._filter)
        self._set_app_sheet(ctx, None)

    def on_config(self, ctx: Any, cfg: dict, changed: frozenset) -> None:
        if changed & {"enabled", "accent", "density", "surfaces.qt_chrome"} or not changed:
            self.apply(ctx)

    # -------------------------------------------------------------------

    def _wanted(self, ctx: Any) -> bool:
        cfg = ctx.config.get()
        return bool(cfg.get("enabled") and cfg["surfaces"].get(self.id))

    def _block(self, ctx: Any) -> str:
        from aqt.theme import theme_manager

        cfg = ctx.config.get()
        return qss.render(tokens.tokens(theme_manager.night_mode, cfg["accent"], cfg["density"]))

    def _on_style(self, ctx: Any, buf: str) -> str:
        buf = qss.strip(buf)
        return qss.splice(buf, self._block(ctx)) if self._wanted(ctx) else buf

    def apply(self, ctx: Any) -> None:
        self._set_app_sheet(ctx, self._block(ctx) if self._wanted(ctx) else None)

    def _set_app_sheet(self, ctx: Any, block: str | None) -> None:
        app = ctx.mw.app
        current = app.styleSheet() or ""
        new = qss.splice(current, block) if block else qss.strip(current)
        if new != current:
            app.setStyleSheet(new)

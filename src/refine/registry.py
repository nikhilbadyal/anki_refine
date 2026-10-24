"""Owns the surfaces and the shared webview plumbing.

Every Refine CSS rule is scoped under html.refine plus per-surface classes
(html.rf-s-<surface>, html.rf-h-<home panel>, ...). Toggling features
therefore only toggles classes in the open webviews; nothing is re-rendered
(re-rendering the reviewer would drop a revealed answer, see M0 report Q5).
Token changes (accent, density) replace <style id="rf-tokens"> in place.
"""

from __future__ import annotations

import json
from typing import Any

from aqt import gui_hooks

from .context import Context
from .surfaces.base import Surface, WebSurface
from .surfaces.deck_browser import DeckBrowserSurface
from .surfaces.overview import OverviewSurface
from .surfaces.qt_chrome import QtChromeSurface
from .surfaces.reviewer import ReviewerSurface
from .surfaces.toolbar import ToolbarSurface
from .theme import css as theme_css

BRIDGE_PREFIX = "refine:"


class Registry:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.surfaces: list[Surface] = [
            ToolbarSurface(),
            DeckBrowserSurface(),
            OverviewSurface(),
            ReviewerSurface(),
            QtChromeSurface(),
        ]
        self.started = False
        self.skipped: dict[str, str] = {}

    # ------------------------------------------------------------ lifecycle

    def start(self) -> None:
        if self.started:
            return
        self.started = True
        g = self.ctx.guard
        gui_hooks.webview_will_set_content.append(g.wrap("core", self._on_set_content))
        gui_hooks.webview_did_receive_js_message.append(
            g.wrap("core", self._on_js_message, is_filter=True)
        )
        for s in self.surfaces:
            missing = [h for h in s.requires_hooks if not hasattr(gui_hooks, h)]
            if missing:
                self.skipped[s.id] = f"missing hooks: {', '.join(missing)}"
                self.ctx.log.warning("surface %s skipped: %s", s.id, self.skipped[s.id])
                continue
            try:
                s.install(self.ctx)
            except Exception:
                self.ctx.log.exception("surface %s failed to install", s.id)
                self.skipped[s.id] = "install failed"
        # The first render of the toolbar and deck browser can happen before
        # main_window_did_init on some platforms; redraw once so they pick up
        # our assets.
        self.refresh_screens(toolbar=True)

    def active_surfaces(self) -> list[Surface]:
        return [s for s in self.surfaces if s.id not in self.skipped and not self.ctx.guard.is_disabled(s.id)]

    # ------------------------------------------------------- web content

    def flags(self, cfg: dict[str, Any]) -> dict[str, bool]:
        """Every html class Refine manages -> whether it should be set."""
        on = bool(cfg.get("enabled"))
        out: dict[str, bool] = {"refine": on}
        active = {s.id for s in self.active_surfaces()}
        for s in self.surfaces:
            out[f"rf-s-{s.id}"] = on and s.id in active and bool(cfg["surfaces"].get(s.id))
            for k, v in s.flags(cfg).items():
                out[k] = on and v
        out["rf-compact"] = on and cfg.get("density") == "compact"
        return out

    def _on_set_content(self, web_content: Any, context: Any) -> None:
        cfg = self.ctx.config.get()
        if not cfg.get("enabled"):
            return
        name = type(context).__name__ if context is not None else ""
        matched = [
            s for s in self.active_surfaces() if isinstance(s, WebSurface) and name in s.contexts
        ]
        if not matched:
            return
        base = self.ctx.web_base
        # rf-page-* tells pages that share a surface stylesheet apart (e.g. the
        # deck list and its bottom bar are separate webviews)
        classes = [k for k, v in self.flags(cfg).items() if v] + [f"rf-page-{name}"]
        state = getattr(self.ctx.mw, "state", "")
        head = (
            "<script>(function(){var d=document.documentElement;"
            f"d.classList.add.apply(d.classList,{json.dumps(classes)});"
            f"d.dataset.rfState={json.dumps(state)};}})();</script>"
            + theme_css.style_tag(cfg["accent"], cfg["density"])
        )
        web_content.head += head
        web_content.css.append(f"{base}/css/fonts.css")
        web_content.css.append(f"{base}/css/base.css")
        for s in matched:
            for f in s.css:
                path = f"{base}/css/{f}"
                if path not in web_content.css:
                    web_content.css.append(path)
        web_content.js.append(f"{base}/js/refine.js")
        for s in matched:
            self.ctx.guard.wrap(s.id, s.contribute)(self.ctx, web_content, context, cfg)

    def _on_js_message(self, handled: tuple, message: Any, context: Any) -> tuple:
        if not isinstance(message, str) or not message.startswith(BRIDGE_PREFIX):
            return handled
        cmd = message[len(BRIDGE_PREFIX):]
        for s in self.active_surfaces():
            if cmd.startswith(s.id + ":"):
                self.ctx.guard.wrap(s.id, s.on_bridge)(self.ctx, cmd[len(s.id) + 1 :], context)
                break
        return (True, None)

    # ------------------------------------------------------ live updates

    def webviews(self) -> list[Any]:
        mw = self.ctx.mw
        out = []
        for attr in ("web", "toolbarWeb", "bottomWeb"):
            w = getattr(mw, attr, None)
            if w is not None:
                out.append(w)
        return out

    def push_live(self, cfg: dict[str, Any]) -> None:
        payload = json.dumps(
            {
                "flags": self.flags(cfg),
                "tokens": theme_css.root_css(cfg["accent"], cfg["density"]),
                "styleId": theme_css.STYLE_ID,
            }
        )
        for w in self.webviews():
            try:
                w.eval(f"window.rfApply && window.rfApply({payload});")
            except Exception:
                self.ctx.log.exception("live update failed")

    def refresh_screens(self, toolbar: bool = False) -> None:
        mw = self.ctx.mw
        try:
            if toolbar and getattr(mw, "toolbar", None) is not None:
                mw.toolbar.draw()
            state = getattr(mw, "state", None)
            if state == "deckBrowser":
                mw.deckBrowser.refresh()
            elif state == "overview":
                mw.overview.refresh()
        except Exception:
            self.ctx.log.exception("refresh failed")

    def on_config(self, cfg: dict[str, Any], changed: frozenset) -> None:
        if "enabled" in changed and cfg.get("enabled"):
            # webviews rendered while disabled lack our assets
            self.refresh_screens(toolbar=True)
        if any(p.startswith("home.") for p in changed):
            self.refresh_screens()
        self.push_live(cfg)
        for s in self.active_surfaces():
            self.ctx.guard.wrap(s.id, s.on_config)(self.ctx, cfg, changed)

    def disable_after_errors(self, surface_id: str) -> None:
        cfg = self.ctx.config.get()
        self.push_live(cfg)  # flags() now excludes the disabled surface
        for s in self.surfaces:
            if s.id == surface_id:
                try:
                    s.uninstall(self.ctx)
                except Exception:
                    self.ctx.log.exception("uninstall of %s failed", surface_id)
        try:
            from aqt.utils import tooltip

            tooltip(f"Refine turned off “{surface_id}” after an error. See Tools ▸ Refine ▸ Diagnostics.", period=6000)
        except Exception:
            pass

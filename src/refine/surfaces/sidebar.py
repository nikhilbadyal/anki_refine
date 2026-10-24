"""The design's app shell: a left sidebar and a header on the Home, Overview
and Stats screens, with Statistics shown inside the main window.

How it stays on public ground:
- The sidebar and header are added to pages Refine already styles
  (webview_will_set_content; for SvelteKit pages, after load).
- Stats is a main-window state of its own: mw.moveToState() accepts any
  state name and fires state_did_change, where Refine loads Anki's own
  statistics page ("graphs", as aqt/stats.py does) into the main webview.
- Every button runs the same Anki function as the stock toolbar or shortcut.
- The stock top toolbar is hidden on these screens only (it returns while
  reviewing). Links other add-ons put in it are offered in the sidebar.
Turning the surface off restores the classic layout and the Stats window.
"""

from __future__ import annotations

from typing import Any

from aqt import gui_hooks

from .. import shell
from .base import WebSurface
from .pages import inject_page

STATS_STATE = "refineStats"
SHELL_STATES = ("deckBrowser", "overview", STATS_STATE)


class SidebarSurface(WebSurface):
    id = "sidebar"
    requires_hooks = (
        "webview_will_set_content",
        "state_did_change",
        "top_toolbar_did_init_links",
        "webview_did_inject_style_into_page",
    )
    # TopToolbar: only for the stylesheet that hides it on shell screens
    contexts = ("DeckBrowser", "Overview", "TopToolbar", "RefineStatsBottomBar")
    css = ("shell.css",)

    def __init__(self) -> None:
        self._extras: list[tuple[str, str]] = []
        self._stats_shortcuts: list[Any] = []
        self._view: Any = None  # Refine's Stats webview (created on first use)
        self._stats_loaded = False
        self._bottom: Any = None

    # ----------------------------------------------------------- lifecycle

    def install(self, ctx: Any) -> None:
        g = ctx.guard
        self._links_hook = g.wrap(self.id, lambda links, tb: self._on_links(ctx, links, tb))
        self._state_hook = g.wrap(self.id, lambda new, old: self._on_state(ctx, new, old))
        self._page_hook = g.wrap(self.id, lambda web: self._on_page(ctx, web))
        gui_hooks.top_toolbar_did_init_links.append(self._links_hook)
        gui_hooks.state_did_change.append(self._state_hook)
        gui_hooks.webview_did_inject_style_into_page.append(self._page_hook)
        self._route_stats_entry_points(ctx)

    def uninstall(self, ctx: Any) -> None:
        gui_hooks.top_toolbar_did_init_links.remove(self._links_hook)
        gui_hooks.state_did_change.remove(self._state_hook)
        gui_hooks.webview_did_inject_style_into_page.remove(self._page_hook)
        if getattr(ctx.mw, "state", "") == STATS_STATE:
            ctx.mw.moveToState("deckBrowser")

    def active(self, ctx: Any) -> bool:
        cfg = ctx.config.get()
        return bool(cfg.get("enabled") and cfg["surfaces"].get(self.id)) and not ctx.guard.is_disabled(self.id)

    def on_config(self, ctx: Any, cfg: dict, changed: frozenset) -> None:
        if not changed & {"enabled", "surfaces.sidebar"}:
            return
        mw = ctx.mw
        if mw.state == STATS_STATE and not self.active(ctx):
            mw.moveToState("deckBrowser")
        elif mw.state == "deckBrowser":
            mw.deckBrowser.refresh()
        elif mw.state == "overview":
            mw.overview.refresh()
        web = getattr(mw, "toolbarWeb", None)
        if web is not None:
            web.adjustHeightToFit()  # the toolbar shows/hides with the shell

    # ------------------------------------------------------------- markup

    def _on_links(self, ctx: Any, links: list[str], toolbar: Any) -> None:
        self._extras = shell.extra_toolbar_links(links)
        # create_link() re-registers handlers on every toolbar draw; re-route
        # the Stats link each time
        if isinstance(getattr(toolbar, "link_handlers", None), dict):
            toolbar.link_handlers["stats"] = self._stats_handler

    def _profile(self, ctx: Any) -> str:
        return getattr(ctx.mw.pm, "name", "") or ""

    def contribute(self, ctx: Any, web_content: Any, context: Any, cfg: dict) -> None:
        name = type(context).__name__
        # the toolbar and bottom bars only take the stylesheet, never the shell
        if name not in ("DeckBrowser", "Overview") or not self.active(ctx):
            return
        col = ctx.mw.col
        if name == "DeckBrowser":
            decks = len(col.decks.all_names_and_ids(skip_empty_default=True))
            title = "Decks"
            sub = f"{decks} deck{'s' if decks != 1 else ''} · {col.card_count():,} cards"
        else:
            title, sub = col.decks.current()["name"], "Deck overview"
        web_content.body = (
            shell.sidebar_html("decks", self._profile(ctx), self._extras)
            + shell.header_html(title, sub)
            + web_content.body
        )

    def _on_page(self, ctx: Any, web: Any) -> None:
        mw = ctx.mw
        if not self.active(ctx):
            return
        url = web.url().toString()
        is_stats_view = web is self._view and self._view is not None
        if not is_stats_view and web is not getattr(mw, "web", None):
            return
        if is_stats_view and "graphs" in url:
            page, active, title = "stats", "stats", "Statistics"
            css: tuple[str, ...] = ("pages.css", "shell.css")
            surface = "pages"
        elif mw.state == "overview" and "congrats" in url:
            page, active, title = "congrats", "decks", mw.col.decks.current()["name"]
            css, surface = ("congrats.css", "shell.css"), "overview"
        else:
            return
        inject_page(
            ctx,
            web,
            surface,
            page,
            css,
            extra_classes=("rf-s-sidebar",),
            prepend_html=shell.sidebar_html(active, self._profile(ctx), self._extras)
            + shell.header_html(title),
        )

    # ------------------------------------------------------- stats state

    # Anki only gives its backend API to trusted webview kinds; the main
    # webview (which can show third-party content) deliberately has none.
    # So Stats gets its own webview of the kind Anki's Stats window uses,
    # shown in the main window's layout in place of the main webview.
    def _stats_view(self, ctx: Any) -> Any:
        if self._view is None:
            from aqt.webview import AnkiWebView, AnkiWebViewKind

            mw = ctx.mw
            view = AnkiWebView(parent=mw, kind=AnkiWebViewKind.DECK_STATS)
            view._refine_shell = True  # PagesSurface leaves it to us
            view.set_bridge_command(lambda cmd: self._stats_bridge(ctx, cmd), self)
            view.hide()
            layout = mw.mainLayout
            layout.insertWidget(layout.indexOf(mw.web) + 1, view)
            self._view = view
        return self._view

    def _on_state(self, ctx: Any, new: str, old: str) -> None:
        mw = ctx.mw
        if new == STATS_STATE:
            view = self._stats_view(ctx)
            from aqt.qt import QColor
            from aqt.theme import theme_manager

            from ..theme.tokens import tokens

            cfg = ctx.config.get()
            bg = tokens(theme_manager.night_mode, cfg["accent"], cfg["density"])["bg"]
            view.page().setBackgroundColor(QColor(bg))  # no grey flash while it loads
            mw.web.hide()
            view.show()
            # cache-bust once per session (fresh code after an Anki update);
            # later visits reuse the cached page bundle, the data is always new
            view.load_sveltekit_page("graphs", cache_bust=not self._stats_loaded)
            self._stats_loaded = True
            self._draw_stats_bottom(ctx)
        elif old == STATS_STATE:
            if self._view is not None:
                self._view.hide()
            mw.web.show()

    def _draw_stats_bottom(self, ctx: Any) -> None:
        """Bottom bar while Stats is shown: Save PDF, as in Anki's Stats window."""
        from aqt.toolbar import BottomBar

        class RefineStatsBottomBar:
            pass

        if self._bottom is None:
            self._bottom = BottomBar(ctx.mw, ctx.mw.bottomWeb)
        self._bottom.draw(
            buf="<button onclick=\"pycmd('pdf');\">Save PDF</button>",
            link_handler=lambda cmd: self._save_pdf(ctx) if cmd == "pdf" else None,
            web_context=RefineStatsBottomBar(),
        )

    def _save_pdf(self, ctx: Any) -> None:
        # same steps as aqt/stats.py NewDeckStats.saveImage
        import time

        from aqt.utils import getSaveFile, tooltip

        view = self._view
        if view is None:
            return
        name = time.strftime("anki-stats-%Y-%m-%d@%H-%M-%S.pdf", time.localtime())
        path = getSaveFile(ctx.mw, title="Save PDF", dir_description="stats", key="stats", ext=".pdf", fname=name)
        if not path:
            return

        def after_scroll(_: Any) -> None:
            view.page().printToPdf(path)
            tooltip("Saved.")

        view.evalWithCallback("window.scrollTo(0, 0);", after_scroll)

    def _stats_bridge(self, ctx: Any, cmd: str) -> bool:
        # same as aqt/stats.py NewDeckStats._on_bridge_cmd
        if cmd.startswith("browserSearch"):
            import aqt

            _, query = cmd.split(":", 1)
            aqt.dialogs.open("Browser", ctx.mw).search_for(query)
        return False

    def open_stats(self, ctx: Any) -> None:
        mw = ctx.mw
        if not self.active(ctx):
            mw.onStats()
            return
        if mw.state == STATS_STATE and self._view is not None:
            self._view.load_sveltekit_page("graphs", cache_bust=True)
        else:
            mw.moveToState(STATS_STATE)

    def _route_stats_entry_points(self, ctx: Any) -> None:
        """Make "T" and the toolbar's Stats link open the in-window Stats when
        the shell is on (the stock window otherwise)."""
        mw = ctx.mw
        handler = ctx.guard.wrap(self.id, lambda: self.open_stats(ctx))
        self._stats_handler = handler
        tb = getattr(mw, "toolbar", None)
        if tb is not None and isinstance(getattr(tb, "link_handlers", None), dict):
            tb.link_handlers["stats"] = handler
        try:
            from aqt.qt import QShortcut

            for sc in mw.findChildren(QShortcut):
                if sc.key().toString() in ("T", "Shift+T"):
                    sc.activated.disconnect()
                    sc.activated.connect(handler)
                    self._stats_shortcuts.append(sc)
        except Exception:
            ctx.log.exception("could not route the Stats shortcut")

    # -------------------------------------------------------------- bridge

    def on_bridge(self, ctx: Any, cmd: str, context: Any) -> None:
        verb, _, arg = cmd.partition(":")
        mw = ctx.mw
        if verb == "go":
            if arg == "decks":
                mw.moveToState("deckBrowser")
            elif arg == "stats":
                self.open_stats(ctx)
            elif arg == "browse":
                mw.onBrowse()
            elif arg == "add":
                mw.onAddCard()
            elif arg == "sync":
                mw.on_sync_button_clicked()
            elif arg == "theme":
                # same setting as Preferences > Theme; Anki redraws every screen
                from aqt.theme import Theme, theme_manager

                mw.set_theme(Theme.LIGHT if theme_manager.night_mode else Theme.DARK)
            elif arg == "options":
                from aqt.deckoptions import display_options_for_deck

                display_options_for_deck(mw.col.decks.current())
        elif verb == "toolbar":
            fn = getattr(mw.toolbar, "link_handlers", {}).get(arg)
            if fn is not None:
                fn()
        elif verb == "search":
            import aqt

            browser = aqt.dialogs.open("Browser", mw)
            if arg.strip():
                browser.search_for(arg.strip())

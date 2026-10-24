"""Captures full-window screenshots of Anki's screens in light and dark theme.

Results go to $REFINE_UI_OUT/<theme>_<screen>.png and $REFINE_UI_OUT/shots.json.
The probe seeds and reviews cards, so it only runs in an isolated profile.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable

from aqt import gui_hooks
from aqt.qt import QApplication, QTimer

SETTLE_MS = 900
THEME_MS = 1500
STEP_TIMEOUT_MS = 30_000

Next = Callable[[], None]

_probe: Probe | None = None


def install(out_dir: str) -> None:
    global _probe
    _probe = Probe(Path(out_dir))
    _probe.register_hooks()


def _mw() -> Any:
    from aqt import mw

    return mw


class Probe:
    def __init__(self, out: Path) -> None:
        self.out = out
        out.mkdir(parents=True, exist_ok=True)
        self.t0 = time.time()
        self.r: dict[str, Any] = {"errors": [], "steps": {}, "shots": {}}
        self.waiters: dict[str, list[Callable[[], None]]] = {}
        self.started = False
        self.refine_pkg: str | None = None
        self.ctx: Any = None
        self.original_theme: Any = None

    # ------------------------------------------------------------------ util

    def err(self, where: str) -> None:
        self.r["errors"].append({"where": where, "trace": traceback.format_exc()})

    def later(self, ms: int, fn: Callable[[], None]) -> None:
        QTimer.singleShot(ms, fn)

    def fire(self, name: str) -> None:
        for cb in self.waiters.pop(name, []):
            self.later(SETTLE_MS, cb)

    def wait_for(self, name: str, cb: Callable[[], None], timeout_ms: int) -> None:
        done = {"v": False}

        def ok() -> None:
            if not done["v"]:
                done["v"] = True
                cb()

        def timeout() -> None:
            if not done["v"]:
                done["v"] = True
                self.r["errors"].append({"where": f"wait:{name}", "trace": "timeout"})
                cb()

        self.waiters.setdefault(name, []).append(ok)
        self.later(timeout_ms, timeout)

    def chain(self, steps: list[tuple[str, Callable[[Next], None]]]) -> None:
        if not steps:
            return
        (name, fn), rest = steps[0], steps[1:]
        state = {"done": False}
        started = time.time()

        def nxt() -> None:
            if state["done"]:
                return
            state["done"] = True
            self.r["steps"][name] = {"seconds": round(time.time() - started, 2)}
            self.later(SETTLE_MS, lambda: self.chain(rest))

        def timeout() -> None:
            if not state["done"]:
                self.r["errors"].append({"where": f"step:{name}", "trace": "timeout"})
                nxt()

        self.later(STEP_TIMEOUT_MS, timeout)
        try:
            fn(nxt)
        except Exception:
            self.err(f"step:{name}")
            nxt()

    # ----------------------------------------------------------------- hooks

    def register_hooks(self) -> None:
        gui_hooks.deck_browser_did_render.append(self.on_deck_browser_did_render)
        gui_hooks.overview_did_refresh.append(lambda *a: self.fire("overview_did_refresh"))
        gui_hooks.reviewer_did_show_question.append(lambda *a: self.fire("reviewer_did_show_question"))
        gui_hooks.reviewer_did_show_answer.append(lambda *a: self.fire("reviewer_did_show_answer"))

    def on_deck_browser_did_render(self, *args: Any) -> None:
        self.fire("deck_browser_did_render")
        if not self.started:
            self.started = True
            self.later(1500, self.start)

    # ------------------------------------------------------------- sequence

    def start(self) -> None:
        mw = _mw()
        base = str(getattr(mw.pm, "base", ""))
        self.r["base_folder"] = base
        if ".anki-dev" not in base.replace("\\", "/"):
            self.r["errors"].append({"where": "safety", "trace": f"refusing to run outside .anki-dev: {base}"})
            self.write()
            return
        try:
            from anki.buildinfo import version

            self.r["anki"] = version
        except Exception:
            self.err("version")
        self.find_refine()
        self.original_theme = mw.pm.theme()
        steps: list[tuple[str, Callable[[Next], None]]] = [("seed", self.step_seed), ("resize", self.step_resize)]
        for theme in ("light", "dark"):
            steps += [
                (f"{theme}:theme", lambda n, t=theme: self.step_theme(t, n)),
                (f"{theme}:deck_browser", lambda n, t=theme: self.step_deck_browser(t, n)),
                (f"{theme}:overview", lambda n, t=theme: self.step_overview(t, n)),
                (f"{theme}:reviewer_question", lambda n, t=theme: self.step_question(t, n)),
                (f"{theme}:reviewer_answer", lambda n, t=theme: self.step_answer(t, n)),
                (f"{theme}:back", self.step_back),
                (f"{theme}:settings", lambda n, t=theme: self.step_settings(t, n)),
                (f"{theme}:menu", lambda n, t=theme: self.step_menu(t, n)),
                (f"{theme}:browser", lambda n, t=theme: self.step_browser(t, n)),
                (f"{theme}:narrow", lambda n, t=theme: self.step_narrow(t, n)),
            ]
        steps.append(("cards", self.step_cards))
        steps.append(("study_buttons", self.step_study_buttons))
        steps.append(("finish", self.step_finish))
        self.chain(steps)

    def find_refine(self) -> None:
        mw = _mw()
        try:
            for name in mw.addonManager.allAddons():
                if name.lower().startswith("refine") and "probe" not in name.lower():
                    self.refine_pkg = name
            self.r["refine_addon_folder"] = self.refine_pkg
            if self.refine_pkg:
                self.ctx = getattr(sys.modules.get(self.refine_pkg), "_ctx", None)
            self.r["refine_ctx_available"] = self.ctx is not None
        except Exception:
            self.err("find_refine")

    # ---------------------------------------------------------------- grab

    def shoot(self, theme: str, screen: str) -> None:
        mw = _mw()
        name = f"{theme}_{screen}"
        path = self.out / f"{name}.png"
        n_err = len(self.r["errors"])
        entry: dict[str, Any] = {"file": path.name}
        try:
            # mw.grab() renders the webviews too; screen.grabWindow is opt-in
            # (REFINE_UI_GRAB=screen) because it captures whatever is on screen.
            if os.environ.get("REFINE_UI_GRAB") == "screen":
                img = mw.screen().grabWindow(int(mw.winId())).toImage()
                method = "screen.grabWindow"
            else:
                img = mw.grab().toImage()
                method = "mw.grab"
            img.save(str(path), "PNG")
            entry.update(method=method, size=[img.width(), img.height()])
        except Exception:
            self.err(f"shoot:{name}")
        entry["new_errors"] = self.r["errors"][n_err:]
        self.r["shots"][name] = entry

    # ---------------------------------------------------------------- steps

    def step_seed(self, nxt: Next) -> None:
        mw = _mw()
        col = mw.col
        seed: dict[str, Any] = {}
        if os.environ.get("REFINE_UI_NOSEED") == "1":
            # restored real collection: leave it as it is
            seed["skipped"] = "REFINE_UI_NOSEED"
            self.r["seed"] = seed
            nxt()
            return
        if col.decks.id_for_name("M0 Probe"):
            seed["skipped"] = "already seeded"
        else:
            parent = col.decks.id("M0 Probe")
            child = col.decks.id("M0 Probe::Child")
            col.decks.id("M0 Empty")
            model = col.models.by_name("Basic") or col.models.all()[0]

            def add(did: int, front: str, back: str) -> Any:
                note = col.new_note(model)
                note.fields[0] = front
                note.fields[1] = back
                col.add_note(note, did)
                return note

            add(parent, "<ruby>日本<rt>にほん</rt></ruby>語", "Japanese")
            add(parent, "Parent card 2", "back")
            add(parent, "Parent card 3", "back")
            add(parent, "Parent card 4", "back")
            add(parent, "Parent card 5", "back")
            add(child, "Child card 1", "back")
            add(child, "Child card 2", "back")
            review = add(child, "Child review card", "back")
            try:
                col.sched.set_due_date([c.id for c in review.cards()], "0")
                seed["review_due"] = True
            except Exception:
                self.err("seed:set_due_date")
            try:
                fid = col.decks.new_filtered("M0 Filtered")
                deck = col.decks.get(fid)
                deck["terms"] = [['"deck:M0 Probe::Child" "front:Child card 2"', 10, 0]]
                col.decks.save(deck)
                col.sched.rebuild_filtered_deck(fid)
                seed["filtered"] = True
            except Exception:
                self.err("seed:filtered")
            col.decks.select(parent)
            seed["created"] = True
        self.r["seed"] = seed
        self.wait_for("deck_browser_did_render", nxt, 10_000)
        mw.deckBrowser.refresh()

    def step_resize(self, nxt: Next) -> None:
        mw = _mw()
        mw.showNormal()
        mw.resize(1280, 820)
        nxt()

    def step_theme(self, theme: str, nxt: Next) -> None:
        from aqt.theme import Theme

        _mw().set_theme(Theme.LIGHT if theme == "light" else Theme.DARK)
        self.later(THEME_MS, nxt)

    def step_deck_browser(self, theme: str, nxt: Next) -> None:
        mw = _mw()

        def go() -> None:
            self.shoot(theme, "deck_browser")
            nxt()

        self.wait_for("deck_browser_did_render", go, 10_000)
        mw.deckBrowser.refresh()

    def step_overview(self, theme: str, nxt: Next) -> None:
        mw = _mw()
        probe_deck = mw.col.decks.id_for_name("M0 Probe")
        if probe_deck:
            mw.col.decks.select(probe_deck)
        else:
            # real collection: the first top-level deck with cards waiting
            for node in mw.col.sched.deck_due_tree().children:
                if node.new_count + node.learn_count + node.review_count:
                    mw.col.decks.select(node.deck_id)
                    break

        def go() -> None:
            self.shoot(theme, "overview")
            nxt()

        self.wait_for("overview_did_refresh", go, 10_000)
        mw.moveToState("overview")

    def step_question(self, theme: str, nxt: Next) -> None:
        mw = _mw()

        def go() -> None:
            self.shoot(theme, "reviewer_question")
            nxt()

        self.wait_for("reviewer_did_show_question", go, 10_000)
        mw.moveToState("review")

    def step_answer(self, theme: str, nxt: Next) -> None:
        mw = _mw()

        def go() -> None:
            self.shoot(theme, "reviewer_answer")
            nxt()

        self.wait_for("reviewer_did_show_answer", go, 10_000)
        mw.reviewer.bottom.web.eval('pycmd("ans")')

    # Opt-in card layer: furigana hidden on the question, shown on the answer.
    def step_cards(self, nxt: Next) -> None:
        mw = _mw()
        out: dict[str, Any] = {}
        self.r["cards_layer"] = out
        if self.ctx is None or not mw.col.decks.id_for_name("M0 Probe"):
            out["skipped"] = "needs Refine _ctx and the seeded M0 Probe deck"
            nxt()
            return
        probe_js = (
            "(function(){var rt=document.querySelector('#qa rt');"
            "return JSON.stringify({html:document.documentElement.className,"
            "rt: rt ? getComputedStyle(rt).visibility : null});})()"
        )
        self.ctx.config.update({"cards.japanese": True, "cards.furigana_hover": True})
        mw.col.decks.select(mw.col.decks.id_for_name("M0 Probe"))

        def on_question() -> None:
            mw.web.grab().save(str(self.out / "cards_question.png"), "PNG")

            def got(v: Any) -> None:
                out["question"] = json.loads(v) if isinstance(v, str) else v
                self.wait_for("reviewer_did_show_answer", on_answer, 10_000)
                mw.reviewer.bottom.web.eval('pycmd("ans")')

            mw.web.evalWithCallback(probe_js, got)

        def on_answer() -> None:
            mw.web.grab().save(str(self.out / "cards_answer.png"), "PNG")

            def got(v: Any) -> None:
                out["answer"] = json.loads(v) if isinstance(v, str) else v
                self.ctx.config.update({"cards.japanese": False, "cards.furigana_hover": False})
                self.wait_for("deck_browser_did_render", nxt, 10_000)
                mw.moveToState("deckBrowser")

            mw.web.evalWithCallback(probe_js, got)

        self.wait_for("reviewer_did_show_question", on_question, 10_000)
        mw.moveToState("review")

    # Refine's own actions: the hero and per-row Study buttons must open the
    # reviewer on the right deck (pycmd bridge -> set_current_deck -> review).
    def step_study_buttons(self, nxt: Next) -> None:
        mw = _mw()
        out: dict[str, Any] = {}
        self.r["study_buttons"] = out

        def record(key: str, then: Next) -> None:
            out[key] = {
                "state": mw.state,
                "current_deck": mw.col.decks.name(mw.col.decks.get_current_id()),
            }
            self.wait_for("deck_browser_did_render", then, 10_000)
            mw.moveToState("deckBrowser")

        def click(selector: str, key: str, then: Next) -> None:
            js = (
                "(function(){var b=document.querySelector(%s);"
                "if(!b) return null; var row=b.closest('tr');"
                "var name=row ? row.querySelector('a.deck').textContent : null; b.click(); return name;})()"
                % json.dumps(selector)
            )

            def clicked(name: Any) -> None:
                out[key + "_target"] = name
                if name is None and "hero" not in key:
                    out[key] = {"error": "button not found"}
                    then()
                    return
                self.wait_for("reviewer_did_show_question", lambda: record(key, then), 8_000)

            mw.web.evalWithCallback(js, clicked)

        def hero() -> None:
            click(".rf-hero .rf-btn-primary", "hero", row)

        def row() -> None:
            # last deck row that has cards waiting (a different deck than the hero's)
            click("tr.deck.rf-has-due:not(.current) .rf-row-study", "row", nxt)

        self.wait_for("deck_browser_did_render", hero, 10_000)
        mw.moveToState("deckBrowser")

    def step_back(self, nxt: Next) -> None:
        mw = _mw()
        self.wait_for("deck_browser_did_render", nxt, 10_000)
        mw.moveToState("deckBrowser")

    def step_settings(self, theme: str, nxt: Next) -> None:
        name = f"{theme}_settings"
        if self.ctx is None or not self.refine_pkg:
            self.r["shots"][name] = {"skipped": "Refine add-on exposes no _ctx"}
            nxt()
            return
        mod = importlib.import_module(f"{self.refine_pkg}.ui.settings_dialog")

        def grab() -> None:
            dlg = None
            for w in QApplication.topLevelWidgets():
                if w.objectName() == "RefineSettings" and w.isVisible():
                    dlg = w
            if dlg is None:
                self.r["shots"][name] = {"error": "RefineSettings dialog not found"}
            else:
                try:
                    dlg.grab().save(str(self.out / f"{name}.png"), "PNG")
                    self.r["shots"][name] = {"file": f"{name}.png", "method": "dialog.grab"}
                except Exception:
                    self.err(f"shoot:{name}")
                dlg.close()
            self.later(SETTLE_MS, nxt)

        self.later(800, grab)
        mod.open_settings(self.ctx)

    # Qt-side styling (QSS): an open Tools menu and the card browser window.
    def step_menu(self, theme: str, nxt: Next) -> None:
        from aqt.qt import QPoint

        mw = _mw()
        name = f"{theme}_menu_tools"
        menu = mw.form.menuTools

        def grab() -> None:
            try:
                menu.grab().save(str(self.out / f"{name}.png"), "PNG")
                self.r["shots"][name] = {"file": f"{name}.png", "method": "menu.grab"}
            except Exception:
                self.err(f"shoot:{name}")
            menu.hide()
            self.later(SETTLE_MS, nxt)

        menu.popup(mw.mapToGlobal(QPoint(150, 24)))
        self.later(700, grab)

    def step_browser(self, theme: str, nxt: Next) -> None:
        import aqt

        mw = _mw()
        name = f"{theme}_browser"
        browser = aqt.dialogs.open("Browser", mw)

        def grab() -> None:
            try:
                browser.resize(1280, 760)
                browser.grab().save(str(self.out / f"{name}.png"), "PNG")
                self.r["shots"][name] = {"file": f"{name}.png", "method": "browser.grab"}
            except Exception:
                self.err(f"shoot:{name}")
            try:
                browser.close()
            except Exception:
                self.err(f"close:{name}")
            self.later(1500, nxt)

        self.later(2500, grab)

    def step_narrow(self, theme: str, nxt: Next) -> None:
        mw = _mw()
        mw.resize(900, 700)

        def go() -> None:
            self.shoot(theme, "deck_browser_narrow")
            mw.resize(1280, 820)
            nxt()

        self.wait_for("deck_browser_did_render", go, 10_000)
        mw.deckBrowser.refresh()

    def step_finish(self, nxt: Next) -> None:
        mw = _mw()
        try:
            mw.set_theme(self.original_theme)
        except Exception:
            self.err("restore_theme")
        if self.ctx is not None:
            try:
                self.r["refine_guard_errors"] = list(self.ctx.guard.errors())
            except Exception:
                self.err("guard.errors")
        self.write()
        (self.out / "ui_done").write_text("1")
        nxt()
        if os.environ.get("REFINE_UI_AUTOQUIT") == "1":
            mw.close()

    def write(self) -> None:
        self.r["seconds"] = round(time.time() - self.t0, 1)
        (self.out / "shots.json").write_text(
            json.dumps(self.r, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )

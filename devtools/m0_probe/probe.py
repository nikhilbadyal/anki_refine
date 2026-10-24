"""Drives Anki through its legacy screens, captures HTML snapshots and
answers the M0 questions from PLAN.md:

  Q1 Chromium version / CSS feature support in the webviews
  Q2 legacy class names (snapshots; compared across versions by devenv.py)
  Q3 top-toolbar height behaviour when its CSS grows
  Q4 col.sched.day_cutoff semantics vs rollover and revlog
  Q5 which refresh paths re-run webview_will_set_content in the reviewer

Plus: style_did_init start-up ordering and /_addons web-export serving.

Results go to $REFINE_M0_OUT/probe.json and $REFINE_M0_OUT/snapshots/*.html.
The probe seeds and reviews cards, so it only runs in an isolated profile.
"""

from __future__ import annotations

import datetime
import json
import os
import platform
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable

from aqt import gui_hooks
from aqt.qt import QTimer

SETTLE_MS = 700
STEP_TIMEOUT_MS = 20_000
CDP_WAIT_S = 20

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
        (out / "snapshots").mkdir(parents=True, exist_ok=True)
        self.t0 = time.time()
        self.events: list[dict[str, Any]] = []
        self.content_log: list[dict[str, Any]] = []
        self.r: dict[str, Any] = {"errors": [], "steps": {}}
        self.waiters: dict[str, list[Callable[[], None]]] = {}
        self.toolbar_padding = False
        self.main_window_did_init_seen = False
        self.started = False
        self.style_calls: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ util

    def now(self) -> float:
        return round(time.time() - self.t0, 3)

    def ev(self, event: str, **detail: Any) -> None:
        self.events.append({"t": self.now(), "event": event, **detail})

    def err(self, where: str) -> None:
        self.r["errors"].append({"where": where, "trace": traceback.format_exc()})

    def later(self, ms: int, fn: Callable[[], None]) -> None:
        QTimer.singleShot(ms, fn)

    def fire(self, name: str) -> None:
        self.ev(name)
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

    def js(self, web: Any, code: str, cb: Callable[[Any], None]) -> None:
        try:
            web.evalWithCallback(code, cb)
        except Exception:
            self.err("js")
            cb(None)

    def snap(self, name: str, web: Any, nxt: Next) -> None:
        def got(html: Any) -> None:
            try:
                text = html if isinstance(html, str) else ""
                # keep fixtures diff-stable across runs
                text = re.sub(r"127\.0\.0\.1:\d+", "127.0.0.1:PORT", text)
                (self.out / "snapshots" / f"{name}.html").write_text(
                    text, encoding="utf-8"
                )
                self.r.setdefault("snapshots", {})[name] = {
                    "bytes": len(text),
                    "webview_height": web.height(),
                    "title": getattr(web, "title", None),
                }
            except Exception:
                self.err(f"snap:{name}")
            nxt()

        self.js(web, "document.documentElement.outerHTML", got)

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

        self.ev("step", name=name)
        self.later(STEP_TIMEOUT_MS, timeout)
        try:
            fn(nxt)
        except Exception:
            self.err(f"step:{name}")
            nxt()

    # ----------------------------------------------------------------- hooks

    def register_hooks(self) -> None:
        gui_hooks.style_did_init.append(self.on_style_did_init)
        gui_hooks.webview_will_set_content.append(self.on_webview_will_set_content)
        gui_hooks.main_window_did_init.append(self.on_main_window_did_init)
        gui_hooks.profile_did_open.append(lambda: self.ev("profile_did_open"))
        gui_hooks.deck_browser_did_render.append(self.on_deck_browser_did_render)
        gui_hooks.overview_did_refresh.append(lambda *a: self.fire("overview_did_refresh"))
        gui_hooks.reviewer_did_show_question.append(
            lambda *a: self.fire("reviewer_did_show_question")
        )
        gui_hooks.reviewer_did_show_answer.append(
            lambda *a: self.fire("reviewer_did_show_answer")
        )
        gui_hooks.reviewer_did_answer_card.append(
            lambda *a: self.fire("reviewer_did_answer_card")
        )
        gui_hooks.top_toolbar_did_redraw.append(lambda *a: self.fire("top_toolbar_did_redraw"))
        self.ev("hooks_registered")

    def on_style_did_init(self, buf: str) -> str:
        self.style_calls.append(
            {"t": self.now(), "before_main_window_did_init": not self.main_window_did_init_seen}
        )
        return buf

    def on_webview_will_set_content(self, web_content: Any, context: Any) -> None:
        name = type(context).__name__ if context is not None else None
        self.content_log.append({"t": self.now(), "context": name})
        if self.toolbar_padding and name == "TopToolbar":
            web_content.head += (
                "<style id='rf-m0-pad'>body{padding-top:16px!important;"
                "padding-bottom:16px!important}</style>"
            )

    def on_main_window_did_init(self) -> None:
        self.main_window_did_init_seen = True
        self.ev("main_window_did_init")

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
            self.r["errors"].append(
                {"where": "safety", "trace": f"refusing to run outside .anki-dev: {base}"}
            )
            self.write()
            return
        self.collect_versions()
        self.chain(
            [
                ("seed", self.step_seed),
                ("deck_browser", self.step_deck_browser),
                ("engine_features", self.step_engine_features),
                ("web_exports", self.step_web_exports),
                ("toolbar_height", self.step_toolbar_height),
                ("overview", self.step_overview),
                ("review_question", self.step_review_question),
                ("review_answer", self.step_review_answer),
                ("reviewer_refresh_paths", self.step_refresh_paths),
                ("answer_card", self.step_answer_card),
                ("day_cutoff", self.step_day_cutoff),
                ("deck_browser_after", self.step_deck_browser_after),
                ("theme_toggle", self.step_theme_toggle),
                ("finish", self.step_finish),
            ]
        )

    def collect_versions(self) -> None:
        v: dict[str, Any] = {"python": sys.version, "platform": platform.platform()}
        try:
            from anki.buildinfo import version

            v["anki"] = version
        except Exception:
            self.err("version:anki")
        try:
            from anki.utils import int_version

            v["int_version"] = int_version()
        except Exception:
            self.err("version:int")
        try:
            from aqt.qt import PYQT_VERSION_STR, qVersion

            v["qt"] = qVersion()
            v["pyqt"] = PYQT_VERSION_STR
        except Exception:
            self.err("version:qt")
        try:
            from aqt.qt import qWebEngineChromiumVersion, qWebEngineVersion  # type: ignore

            v["webengine"] = qWebEngineVersion()
            v["chromium_from_qt"] = qWebEngineChromiumVersion()
        except Exception:
            self.err("version:webengine")
        v["frozen_or_installed"] = getattr(sys, "frozen", False) or "Programs" in sys.executable
        v["executable"] = sys.executable
        self.r["versions"] = v

    # Seed an isolated collection with: a parent deck with ruby text, a child
    # with new + review-due cards, an empty deck, and a filtered deck, so all
    # deck-browser row/count variants appear in the snapshots.
    def step_seed(self, nxt: Next) -> None:
        mw = _mw()
        col = mw.col
        seed: dict[str, Any] = {}
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

    def step_deck_browser(self, nxt: Next) -> None:
        mw = _mw()
        self.snap(
            "deck_browser",
            mw.web,
            lambda: self.snap(
                "deck_browser_bottom",
                mw.bottomWeb,
                lambda: self.snap("toolbar", mw.toolbar.web, nxt),
            ),
        )

    def step_engine_features(self, nxt: Next) -> None:
        code = r"""
(function () {
  const sup = (p, v) => { try { return v === undefined ? CSS.supports(p) : CSS.supports(p, v); } catch (e) { return "error"; } };
  const el = document.createElement("div");
  el.id = "rf-m0"; el.className = "a";
  document.body.appendChild(el);
  const st = document.createElement("style");
  st.textContent =
    "@layer rflayer { #rf-m0 { color: rgb(1, 2, 3); } #rf-m0.a { outline-color: rgb(1, 2, 3); } }" +
    "div#rf-m0 { outline-color: rgb(4, 5, 6); }" +
    ".a { & { background-color: rgb(7, 8, 9); } }";
  document.head.appendChild(st);
  const cs = getComputedStyle(el);
  const m = navigator.userAgent.match(/Chrome\/([\d.]+)/);
  const res = {
    userAgent: navigator.userAgent,
    chrome: m ? m[1] : null,
    devicePixelRatio: window.devicePixelRatio,
    prefersReducedMotion: matchMedia("(prefers-reduced-motion: reduce)").matches,
    prefersDark: matchMedia("(prefers-color-scheme: dark)").matches,
    htmlClass: document.documentElement.className,
    bodyClass: document.body.className,
    layer_applies: cs.color === "rgb(1, 2, 3)",
    layer_loses_to_unlayered: cs.outlineColor === "rgb(4, 5, 6)",
    CSSLayerBlockRule: typeof CSSLayerBlockRule !== "undefined",
    nesting: cs.backgroundColor === "rgb(7, 8, 9)",
    supports: {
      where: sup("selector(:where(a))"),
      is: sup("selector(:is(a))"),
      has: sup("selector(:has(a))"),
      focus_visible: sup("selector(:focus-visible)"),
      color_mix: sup("color", "color-mix(in srgb, red 50%, blue)"),
      oklch: sup("color", "oklch(0.6 0.1 250)"),
      container_queries: sup("container-type", "inline-size"),
      mask_image: sup("mask-image", "url(x.svg)"),
      text_wrap_balance: sup("text-wrap", "balance"),
      ruby_position: sup("ruby-position", "over"),
      scrollbar_gutter: sup("scrollbar-gutter", "stable"),
      accent_color: sup("accent-color", "red")
    }
  };
  el.remove(); st.remove();
  return JSON.stringify(res);
})()
"""

        def got(val: Any) -> None:
            try:
                self.r["engine"] = json.loads(val) if isinstance(val, str) else {"raw": val}
            except Exception:
                self.err("engine:parse")
            nxt()

        self.js(_mw().web, code, got)

    def step_web_exports(self, nxt: Next) -> None:
        mw = _mw()
        pkg = None
        try:
            for name in mw.addonManager.allAddons():
                if name.lower().startswith("refine") and "probe" not in name:
                    pkg = name
            self.r["refine_addon_folder"] = pkg
            self.r["refine_module_loaded"] = pkg in sys.modules if pkg else False
        except Exception:
            self.err("web_exports:find")
        if not pkg:
            self.r["web_exports"] = {"error": "refine add-on folder not found"}
            nxt()
            return
        urls = [f"/_addons/{pkg}/web/css/base.css", f"/_addons/{pkg}/config.json"]
        code = (
            "JSON.stringify(%s.map(u => { const x = new XMLHttpRequest();"
            " x.open('GET', u, false); try { x.send(); return [u, x.status, x.getResponseHeader('content-type')]; }"
            " catch (e) { return [u, 'error:' + e, null]; } }))" % json.dumps(urls)
        )

        def got(val: Any) -> None:
            self.r["web_exports"] = json.loads(val) if isinstance(val, str) else val
            nxt()

        self.js(mw.web, code, got)

    # Q3: how does the top toolbar's fixed height react to taller content?
    def step_toolbar_height(self, nxt: Next) -> None:
        mw = _mw()
        tb = mw.toolbar.web
        out: dict[str, Any] = {}
        self.r["toolbar_height"] = out
        measure_js = (
            "JSON.stringify({offsetHeight: document.documentElement.offsetHeight,"
            " scrollHeight: document.documentElement.scrollHeight, innerHeight: window.innerHeight})"
        )
        pad_js = (
            "(function(){const s=document.createElement('style');s.id='rf-m0-late';"
            "s.textContent='body{padding-top:16px!important;padding-bottom:16px!important}';"
            "document.head.appendChild(s);return 1})()"
        )
        unpad_js = "(function(){const s=document.getElementById('rf-m0-late'); if(s) s.remove(); return 1})()"

        def measure(key: str, then: Next, delay: int = 600) -> None:
            def doit() -> None:
                def got(val: Any) -> None:
                    try:
                        d = json.loads(val) if isinstance(val, str) else {}
                    except Exception:
                        d = {}
                    d["qt_widget_height"] = tb.height()
                    out[key] = d
                    then()

                self.js(tb, measure_js, got)

            self.later(delay, doit)

        def baseline() -> None:
            measure("1_baseline", late_inject, 0)

        def late_inject() -> None:
            self.js(tb, pad_js, lambda _v: measure("2_after_late_css", late_adjust))

        def late_adjust() -> None:
            tb.adjustHeightToFit()
            measure("3_after_late_css_then_adjustHeightToFit", late_cleanup, 900)

        def late_cleanup() -> None:
            self.js(tb, unpad_js, lambda _v: (tb.adjustHeightToFit(), measure("4_late_css_removed", render_time, 900)))

        # Toolbar.redraw() only refreshes sync state; Toolbar.draw() re-renders
        # the HTML (re-running webview_will_set_content) and then calls
        # adjustHeightToFit() itself.
        def render_time() -> None:
            self.toolbar_padding = True
            n = len(self.content_log)
            mw.toolbar.draw()
            measure("5_render_time_css_via_draw", lambda: note(n, "5_render_time_css_via_draw", restore), 1500)

        def restore() -> None:
            self.toolbar_padding = False
            n = len(self.content_log)
            mw.toolbar.draw()
            measure("6_restored_via_draw", lambda: note(n, "6_restored_via_draw", nxt), 1500)

        def note(n: int, key: str, then: Next) -> None:
            out[key]["content_hook_contexts"] = [c["context"] for c in self.content_log[n:]]
            then()

        baseline()

    def step_overview(self, nxt: Next) -> None:
        mw = _mw()
        did = mw.col.decks.id_for_name("M0 Probe")
        mw.col.decks.select(did)

        def snaps() -> None:
            self.snap("overview", mw.web, lambda: self.snap("overview_bottom", mw.bottomWeb, nxt))

        self.wait_for("overview_did_refresh", snaps, 10_000)
        mw.moveToState("overview")

    def step_review_question(self, nxt: Next) -> None:
        mw = _mw()

        def snaps() -> None:
            self.snap(
                "reviewer_question",
                mw.web,
                lambda: self.snap("reviewer_bottom_question", mw.bottomWeb, nxt),
            )

        self.wait_for("reviewer_did_show_question", snaps, 10_000)
        mw.moveToState("review")

    def step_review_answer(self, nxt: Next) -> None:
        mw = _mw()

        def snaps() -> None:
            self.snap(
                "reviewer_answer",
                mw.web,
                lambda: self.snap("reviewer_bottom_answer", mw.bottomWeb, nxt),
            )

        self.wait_for("reviewer_did_show_answer", snaps, 10_000)
        mw.reviewer.bottom.web.eval('pycmd("ans")')

    # Q5: which ways of refreshing the reviewer re-run webview_will_set_content,
    # and what do they do to the card being reviewed?
    def step_refresh_paths(self, nxt: Next) -> None:
        mw = _mw()
        out: dict[str, Any] = {}
        self.r["reviewer_refresh_paths"] = out

        def snapshot_state() -> dict[str, Any]:
            rv = mw.reviewer
            return {
                "card_id": rv.card.id if rv.card else None,
                "reviewer_state": rv.state,
                "main_state": mw.state,
                "content_hook_calls": len(self.content_log),
                # Reviewer.op_executed only refreshes immediately when focused
                "window_active": mw.isActiveWindow(),
            }

        def trial(name: str, action: Callable[[], None], wait_ms: int, then: Next) -> None:
            before = snapshot_state()

            def after() -> None:
                a = snapshot_state()
                calls = self.content_log[before["content_hook_calls"] :]
                out[name] = {
                    "before": before,
                    "after": a,
                    "content_hook_contexts": [c["context"] for c in calls],
                    "same_card": before["card_id"] == a["card_id"],
                }
                then()

            try:
                action()
            except Exception:
                self.err(f"refresh:{name}")
            self.later(wait_ms, after)

        def ensure_answer(then: Next) -> None:
            if mw.reviewer.state == "answer":
                then()
                return
            self.wait_for("reviewer_did_show_answer", then, 8000)
            mw.reviewer.bottom.web.eval('pycmd("ans")')

        live_js = (
            "(function(){const s=document.createElement('style');s.id='rf-m0-live';"
            "s.textContent='html body{outline:3px solid rgb(9, 8, 7)}';document.head.appendChild(s);"
            "return getComputedStyle(document.body).outlineColor})()"
        )

        def t_live() -> None:
            before = snapshot_state()

            def got_main(v: Any) -> None:
                def got_bottom(b: Any) -> None:
                    out["js_live_style_injection"] = {
                        "before": before,
                        "after": snapshot_state(),
                        "main_computed_outline": v,
                        "bottom_computed_outline": b,
                        "content_hook_contexts": [
                            c["context"] for c in self.content_log[before["content_hook_calls"] :]
                        ],
                    }
                    ensure_answer(t_refresh_if_needed)

                self.js(mw.bottomWeb, live_js, got_bottom)

            self.js(mw.web, live_js, got_main)

        def t_refresh_if_needed() -> None:
            trial("reviewer.refresh_if_needed()", mw.reviewer.refresh_if_needed, 1200,
                  lambda: ensure_answer(t_reset))

        def t_reset() -> None:
            trial("mw.reset()", mw.reset, 2000, lambda: ensure_answer(t_reenter))

        def t_reenter() -> None:
            trial('mw.moveToState("review")', lambda: mw.moveToState("review"), 2500, nxt)

        t_live()

    def step_answer_card(self, nxt: Next) -> None:
        mw = _mw()
        self.r["revlog_before_answer"] = mw.col.db.scalar("select count() from revlog")

        def answer() -> None:
            self.wait_for("reviewer_did_answer_card", nxt, 8000)
            mw.reviewer.bottom.web.eval('pycmd("ease3")')

        if mw.reviewer.state == "answer":
            answer()
        else:
            self.wait_for("reviewer_did_show_answer", answer, 8000)
            mw.reviewer.bottom.web.eval('pycmd("ans")')

    # Q4: what exactly is day_cutoff, and how do "today" revlog windows line up?
    def step_day_cutoff(self, nxt: Next) -> None:
        mw = _mw()
        col = mw.col
        s = col.sched
        d: dict[str, Any] = {}
        self.r["day_cutoff"] = d
        now = time.time()
        cutoff = s.day_cutoff
        d["now_epoch_s"] = int(now)
        d["day_cutoff"] = cutoff
        d["day_cutoff_type"] = type(cutoff).__name__
        d["seconds_until_cutoff"] = int(cutoff - now)
        d["day_cutoff_local_iso"] = datetime.datetime.fromtimestamp(cutoff).astimezone().isoformat()
        d["sched_today_days_elapsed"] = s.today
        d["col_crt"] = col.crt
        d["days_crt_to_cutoff"] = (cutoff - col.crt) / 86400
        prefs = col.get_preferences()
        rollover = prefs.scheduling.rollover
        d["rollover_hour"] = rollover
        local_now = datetime.datetime.now().astimezone()
        cand = local_now.replace(hour=rollover, minute=0, second=0, microsecond=0)
        if cand <= local_now:
            cand += datetime.timedelta(days=1)
        d["expected_next_rollover_epoch"] = int(cand.timestamp())
        d["matches_next_local_rollover"] = int(cand.timestamp()) == cutoff
        start_ms = (cutoff - 86400) * 1000
        d["revlog_total"] = col.db.scalar("select count() from revlog")
        d["revlog_since_cutoff_minus_1d"] = col.db.scalar(
            "select count() from revlog where id >= ?", start_ms
        )
        d["revlog_time_ms_since_cutoff_minus_1d"] = col.db.scalar(
            "select coalesce(sum(time), 0) from revlog where id >= ?", start_ms
        )
        d["studied_today_string"] = col.studied_today()
        d["has_day_did_change_hook"] = hasattr(gui_hooks, "day_did_change")
        # does day_cutoff follow a rollover change immediately?
        try:
            new_hour = (rollover + 6) % 24
            prefs.scheduling.rollover = new_hour
            col.set_preferences(prefs)
            d["after_rollover_change"] = {"rollover_hour": new_hour, "day_cutoff": s.day_cutoff}
        except Exception:
            self.err("day_cutoff:rollover_change")
        finally:
            prefs.scheduling.rollover = rollover
            col.set_preferences(prefs)
            d["restored_day_cutoff"] = s.day_cutoff
        nxt()

    def step_deck_browser_after(self, nxt: Next) -> None:
        mw = _mw()

        def snaps() -> None:
            self.snap("deck_browser_after_review", mw.web, nxt)

        self.wait_for("deck_browser_did_render", snaps, 10_000)
        mw.moveToState("deckBrowser")

    # Confirms the other half of the start-up finding: style_did_init is
    # missed at start-up but does fire on every later theme change, and
    # webviews switch their night-mode classes without a re-render.
    def step_theme_toggle(self, nxt: Next) -> None:
        mw = _mw()
        from aqt.theme import Theme, theme_manager

        out: dict[str, Any] = {}
        self.r["theme_toggle"] = out
        original = mw.pm.theme()
        start_night = theme_manager.night_mode
        out["original_theme"] = int(original)
        out["start_night_mode"] = start_night
        classes_js = "JSON.stringify([document.documentElement.className, document.body.className])"

        def sample(key: str, then: Next) -> None:
            def got_main(v: Any) -> None:
                def got_tb(t: Any) -> None:
                    out[key] = {
                        "night_mode": theme_manager.night_mode,
                        "style_did_init_calls": len(self.style_calls),
                        "content_hook_calls": len(self.content_log),
                        "main_classes": json.loads(v) if isinstance(v, str) else v,
                        "toolbar_classes": json.loads(t) if isinstance(t, str) else t,
                    }
                    then()

                self.js(mw.toolbar.web, classes_js, got_tb)

            self.js(mw.web, classes_js, got_main)

        def flip() -> None:
            mw.set_theme(Theme.LIGHT if start_night else Theme.DARK)
            self.later(1500, lambda: sample("after_flip", snap_flipped))

        def snap_flipped() -> None:
            self.snap("deck_browser_flipped_theme", mw.web, restore)

        def restore() -> None:
            mw.set_theme(original)
            self.later(1500, lambda: sample("after_restore", nxt))

        sample("before", flip)

    def step_finish(self, nxt: Next) -> None:
        self.write()
        (self.out / "probe_done").write_text("1")
        if os.environ.get("REFINE_M0_AUTOQUIT") != "1":
            nxt()
            return
        deadline = time.time() + CDP_WAIT_S

        def poll() -> None:
            if (self.out / "cdp_done").exists() or time.time() > deadline:
                nxt()
                _mw().close()
            else:
                self.later(500, poll)

        poll()

    def write(self) -> None:
        self.r["style_did_init_calls"] = self.style_calls
        self.r["content_hook_log"] = self.content_log
        self.r["events"] = self.events
        (self.out / "probe.json").write_text(
            json.dumps(self.r, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )

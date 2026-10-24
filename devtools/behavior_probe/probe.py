"""Drives Anki like a user (keys, button clicks, config changes) and records
PASS/FAIL checks in $REFINE_BEHAVIOR_OUT/verify.json. Isolated profiles only."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Generator

from aqt import gui_hooks
from aqt.qt import QApplication, QTimer, Qt

try:
    from aqt.qt import QTest  # type: ignore
except ImportError:
    from PyQt6.QtTest import QTest  # type: ignore

SETTLE = 900
HOOK_TIMEOUT = 10_000
_probe: "Probe | None" = None


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
        self.r: dict[str, Any] = {"checks": [], "errors": [], "hashes": {}, "data": {}}
        self.pending: dict[str, Callable[[tuple], None]] = {}
        self.started = False
        self.ctx: Any = None
        self.refine_pkg: str | None = None
        self.log_path: Path | None = None
        self.log_start = 0

    # ----------------------------------------------------------- recording
    def check(self, cid: str, ok: bool, detail: Any = "") -> None:
        self.r["checks"].append({"id": cid, "result": "PASS" if ok else "FAIL", "detail": detail})

    def skip(self, cid: str, why: str) -> None:
        self.r["checks"].append({"id": cid, "result": "SKIP", "detail": why})

    def err(self, where: str) -> None:
        self.r["errors"].append({"where": where, "trace": traceback.format_exc()})

    def write(self) -> None:
        self.r["seconds"] = round(time.time() - self.t0, 1)
        (self.out / "verify.json").write_text(
            json.dumps(self.r, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )

    # --------------------------------------------------------------- hooks
    def register_hooks(self) -> None:
        def h(name: str) -> Callable[..., None]:
            def f(*a: Any) -> None:
                cb = self.pending.pop(name, None)
                if cb:
                    cb(a)
                if name == "deck_browser_did_render" and not self.started:
                    self.started = True
                    QTimer.singleShot(1500, self.start)

            return f

        for n in (
            "deck_browser_did_render",
            "overview_did_refresh",
            "reviewer_did_show_question",
            "reviewer_did_show_answer",
            "reviewer_did_answer_card",
        ):
            getattr(gui_hooks, n).append(h(n))

    # -------------------------------------------------------------- runner
    def run(self, gen: Generator, value: Any = None) -> None:
        try:
            req = gen.send(value)
        except StopIteration:
            return
        except Exception:
            self.err("script")
            self.finish()
            return
        kind = req[0]
        state = {"done": False}

        def resume(v: Any) -> None:
            if not state["done"]:
                state["done"] = True
                self.run(gen, v)

        if kind == "sleep":
            QTimer.singleShot(req[1], lambda: resume(None))
        elif kind == "hook":
            _, name, trigger, timeout = req
            self.pending[name] = lambda a: QTimer.singleShot(SETTLE, lambda: resume(a))

            def to() -> None:
                if not state["done"]:
                    self.pending.pop(name, None)
                    resume(None)

            QTimer.singleShot(timeout, to)
            try:
                trigger()
            except Exception:
                self.err(f"trigger:{name}")
        elif kind == "js":
            _, web, code = req
            QTimer.singleShot(5000, lambda: resume(None))
            try:
                web.evalWithCallback(code, resume)
            except Exception:
                self.err("js")
                resume(None)

    # ------------------------------------------------------------- helpers
    def key(self, key: Any, mod: Any = Qt.KeyboardModifier.NoModifier) -> None:
        mw = _mw()
        w = QApplication.focusWidget() or mw.web
        QTest.keyClick(w, key, mod)

    def focus_main(self) -> None:
        mw = _mw()
        mw.activateWindow()
        mw.raise_()
        mw.web.setFocus()

    def grab_hash(self, name: str, widget: Any) -> None:
        from aqt.qt import QImage

        img = widget.grab().toImage()
        img.save(str(self.out / f"{name}.png"), "PNG")
        img = img.convertToFormat(QImage.Format.Format_RGB32)
        ptr = img.constBits()
        data = ptr.asstring(img.sizeInBytes())
        self.r["hashes"][name] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": [img.width(), img.height()],
        }

    def classes(self) -> Generator:
        mw = _mw()
        out = {}
        for nm, web in (("main", mw.web), ("toolbar", mw.toolbarWeb), ("bottom", mw.bottomWeb)):
            out[nm] = yield ("js", web, "document.documentElement.className")
        return out

    # -------------------------------------------------------------- start
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
        for name in mw.addonManager.allAddons():
            if name.lower().startswith("refine") and "probe" not in name.lower():
                self.refine_pkg = name
        self.r["refine_addon_folder"] = self.refine_pkg
        if self.refine_pkg:
            self.ctx = getattr(sys.modules.get(self.refine_pkg), "_ctx", None)
            self.log_path = Path(mw.addonManager.addonsFolder(self.refine_pkg)) / "user_files" / "logs" / "refine.log"
            try:
                self.log_start = self.log_path.stat().st_size if self.log_path.exists() else 0
            except OSError:
                self.log_start = 0
        self.r["refine_ctx_available"] = self.ctx is not None
        self.run(self.script())

    def seed(self) -> None:
        # identical to ui_probe.step_seed
        mw = _mw()
        col = mw.col
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
        except Exception:
            self.err("seed:set_due_date")
        try:
            fid = col.decks.new_filtered("M0 Filtered")
            deck = col.decks.get(fid)
            deck["terms"] = [['"deck:M0 Probe::Child" "front:Child card 2"', 10, 0]]
            col.decks.save(deck)
            col.sched.rebuild_filtered_deck(fid)
        except Exception:
            self.err("seed:filtered")
        col.decks.select(parent)

    def finish(self) -> None:
        mw = _mw()
        if self.ctx is not None:
            try:
                self.r["refine_guard_errors"] = self.ctx.guard.errors()
                self.check("D.guard_errors_empty", not self.r["refine_guard_errors"], self.r["refine_guard_errors"])
            except Exception:
                self.err("guard.errors")
        if self.log_path is not None and self.log_path.exists():
            try:
                with self.log_path.open("rb") as f:
                    f.seek(self.log_start)
                    new = f.read().decode("utf-8", "replace")
                lines = new.splitlines()
                self.r["refine_log_new_lines"] = lines[-60:]
                bad = [l for l in lines if "ERROR" in l or "Traceback" in l or "WARNING" in l]
                self.check("D.log_no_errors", not bad, bad[:10])
            except Exception:
                self.err("log")
        self.write()
        (self.out / "behavior_done").write_text("1")
        if os.environ.get("REFINE_BEHAVIOR_AUTOQUIT") == "1":
            mw.close()

    # -------------------------------------------------------------- script
    def to_state(self, state: str) -> None:
        _mw().moveToState(state)

    def script(self) -> Generator:
        from aqt.theme import Theme

        mw = _mw()
        orig_theme = mw.pm.theme()
        try:
            yield from self._script(Theme)
        finally:
            try:
                mw.set_theme(orig_theme)
            except Exception:
                pass
        self.finish()

    def _script(self, Theme: Any) -> Generator:
        mw = _mw()
        self.seed()
        yield ("hook", "deck_browser_did_render", mw.deckBrowser.refresh, HOOK_TIMEOUT)
        mw.showNormal()
        mw.resize(1280, 820)
        yield ("sleep", 800)

        # ---- C: card-area integrity, both themes (first card, unanswered)
        for theme, th in (("light", Theme.LIGHT), ("dark", Theme.DARK)):
            mw.set_theme(th)
            yield ("sleep", 2000)
            try:
                yield ("hook", "reviewer_did_show_question", lambda: self.to_state("review"), HOOK_TIMEOUT)
                yield ("sleep", 1200)
                self.grab_hash(f"card_q_{theme}", mw.web)
                self.r["data"][f"first_card_{theme}"] = mw.reviewer.card.id if mw.reviewer.card else None
                yield ("hook", "reviewer_did_show_answer", lambda: mw.reviewer._showAnswer(), HOOK_TIMEOUT)
                yield ("sleep", 1200)
                self.grab_hash(f"card_a_{theme}", mw.web)
                self.check(f"C.captured_{theme}", True, self.r["hashes"].get(f"card_a_{theme}"))
            except Exception:
                self.err(f"C:{theme}")
                self.check(f"C.captured_{theme}", False, "exception")
            yield ("hook", "deck_browser_did_render", lambda: self.to_state("deckBrowser"), HOOK_TIMEOUT)
        mw.set_theme(Theme.LIGHT)
        yield ("sleep", 2000)

        # ---- A1: deck browser keys
        self.focus_main()
        yield ("sleep", 500)
        self.key(Qt.Key.Key_S)
        yield ("sleep", 2000)
        self.check("A1.s_opens_study", mw.state in ("overview", "review"), f"state={mw.state}")
        self.focus_main()
        self.key(Qt.Key.Key_D)
        yield ("sleep", 2000)
        self.check("A1.d_returns_deckbrowser", mw.state == "deckBrowser", f"state={mw.state}")

        # ---- B: live settings (deck browser)
        if self.ctx is None:
            self.skip("B", "Refine not linked")
        else:
            yield from self.live_settings()

        # ---- A2/A3: reviewer keys and button click
        yield from self.reviewer_keys()

        # ---- B (reviewer): live toggle must not re-render
        if self.ctx is not None:
            yield from self.reviewer_toggle()

    # ----------------------------------------------------------------- B
    def live_settings(self) -> Generator:
        mw = _mw()
        ctx = self.ctx
        self.to_state("deckBrowser")
        yield ("sleep", 1500)
        steps: dict[str, Any] = {}
        accent_js = "getComputedStyle(document.documentElement).getPropertyValue('--rf-accent').trim()"

        def snap(label: str) -> Generator:
            mw.grab().toImage().save(str(self.out / f"B_{label}.png"), "PNG")
            cls = yield from self.classes()
            acc = yield ("js", mw.web, accent_js)
            steps[label] = {"classes": cls, "accent": acc}
            return steps[label]

        try:
            base = yield from snap("a_baseline")
            self.check(
                "B.baseline_refine_classes",
                all("refine" in (v or "").split() for v in base["classes"].values()),
                base["classes"],
            )

            ctx.config.set("accent", "rose")
            yield ("sleep", 1500)
            s = yield from snap("b_accent_rose")
            self.check("B.accent_changes", bool(s["accent"]) and s["accent"] != base["accent"], f"{base['accent']} -> {s['accent']}")

            ctx.config.set("density", "compact")
            yield ("sleep", 1500)
            s = yield from snap("c_compact")
            self.check("B.density_compact", "rf-compact" in (s["classes"]["main"] or "").split(), s["classes"]["main"])

            ctx.config.set("home.activity", False)
            yield ("sleep", 1500)
            s = yield from snap("d_no_activity")
            disp = yield (
                "js",
                mw.web,
                "(function(){var e=document.querySelector('.rf-activity');return e?getComputedStyle(e).display:'MISSING'})()",
            )
            self.check("B.activity_hidden", disp == "none", f"display={disp}; classes={s['classes']['main']}")

            tbl_js = (
                "(function(){var e=document.querySelector('center > table');if(!e)return 'MISSING';"
                "var c=getComputedStyle(e);return [c.backgroundColor,c.borderRadius,c.boxShadow].join(' | ')})()"
            )
            tbl_on = yield ("js", mw.web, tbl_js)
            ctx.config.set("surfaces.deck_browser", False)
            yield ("sleep", 1500)
            s = yield from snap("e_no_deck_surface")
            tbl_off = yield ("js", mw.web, tbl_js)
            self.check(
                "B.surface_off_removes_class",
                "rf-s-deck_browser" not in (s["classes"]["main"] or "").split(),
                s["classes"]["main"],
            )
            self.check("B.surface_off_unstyles_table", tbl_on != tbl_off, f"on={tbl_on} off={tbl_off}")

            ctx.config.set("enabled", False)
            yield ("sleep", 1500)
            s = yield from snap("f_disabled")
            self.check(
                "B.disabled_no_refine_class",
                all("refine" not in (v or "").split() for v in s["classes"].values()),
                s["classes"],
            )

            ctx.config.set("enabled", True)
            yield ("sleep", 1500)
            s = yield from snap("g_reenabled")
            self.check(
                "B.reenabled_restored",
                all("refine" in (v or "").split() for v in s["classes"].values()),
                s["classes"],
            )

            ctx.config.reset()
            yield ("sleep", 1500)
            s = yield from snap("h_reset")
            self.check(
                "B.reset_accent_back",
                s["accent"] == base["accent"] and ctx.config.value("accent") == "jade",
                f"css={s['accent']} (baseline {base['accent']}), cfg={ctx.config.get('accent')}",
            )
        except Exception:
            self.err("B")
            self.check("B.exception", False, traceback.format_exc()[-400:])
        finally:
            try:
                ctx.config.reset()
            except Exception:
                pass
        self.r["data"]["live_settings"] = steps

    # ----------------------------------------------------------------- A2
    def reviewer_keys(self) -> Generator:
        mw = _mw()
        col = mw.col
        K = Qt.Key
        Ctrl = Qt.KeyboardModifier.ControlModifier
        yield ("hook", "reviewer_did_show_question", lambda: self.to_state("review"), HOOK_TIMEOUT)
        yield ("sleep", 800)
        self.focus_main()
        yield ("sleep", 400)

        a = yield ("hook", "reviewer_did_show_answer", lambda: self.key(K.Key_Space), HOOK_TIMEOUT)
        self.check("A2.space_shows_answer", a is not None, f"reviewer.state={mw.reviewer.state}")
        cid = mw.reviewer.card.id
        a = yield ("hook", "reviewer_did_answer_card", lambda: self.key(K.Key_3), HOOK_TIMEOUT)
        ok = a is not None and a[2] == 3 and a[1].id == cid
        self.check("A2.key3_answers_good", ok, None if a is None else {"card": a[1].id, "ease": a[2], "expected_card": cid})
        yield ("sleep", 1200)

        yield ("hook", "reviewer_did_show_answer", lambda: self.key(K.Key_Space), HOOK_TIMEOUT)
        cid = mw.reviewer.card.id
        a = yield ("hook", "reviewer_did_answer_card", lambda: self.key(K.Key_1), HOOK_TIMEOUT)
        ok = a is not None and a[2] == 1 and a[1].id == cid
        self.check("A2.key1_answers_again", ok, None if a is None else {"card": a[1].id, "ease": a[2], "expected_card": cid})
        yield ("sleep", 1500)

        card = mw.reviewer.card
        cid, nid = card.id, card.nid
        self.focus_main()
        self.key(K.Key_1, Ctrl)
        yield ("sleep", 800)
        c = col.get_card(cid)
        self.check("A2.ctrl1_flags_red", c.user_flag() == 1, f"flag={c.user_flag()}")

        self.key(K.Key_Asterisk)
        yield ("sleep", 800)
        marked = col.get_note(nid).has_tag("marked")
        if not marked:
            self.key(K.Key_Asterisk, Qt.KeyboardModifier.ShiftModifier)
            yield ("sleep", 800)
            marked = col.get_note(nid).has_tag("marked")
        self.check("A2.asterisk_marks_note", marked, f"tags={col.get_note(nid).tags}")

        self.key(K.Key_E)
        yield ("sleep", 2000)
        vis = [w for w in QApplication.topLevelWidgets() if w.isVisible()]
        eds = [w for w in vis if "EditCurrent" in (w.objectName() + type(w).__name__)]
        self.check("A2.e_opens_editor", bool(eds), [f"{type(w).__name__}/{w.objectName()}" for w in vis])
        for w in eds:
            w.close()
        yield ("sleep", 1500)
        self.focus_main()
        yield ("sleep", 400)

        cur_id = mw.reviewer.card.id if mw.reviewer.card else None
        self.key(K.Key_Minus)
        yield ("sleep", 1500)
        q = col.get_card(cur_id).queue if cur_id else None
        nxt = mw.reviewer.card.id if mw.reviewer.card else None
        self.check("A2.minus_buries_card", q in (-2, -3), f"queue={q} state={mw.state} next_card_changed={nxt != cur_id}")

        self.focus_main()
        undo_before = col.undo_status().undo
        self.key(K.Key_Z, Ctrl)
        yield ("sleep", 1500)
        q2 = col.get_card(cur_id).queue if cur_id else None
        self.check(
            "A2.ctrl_z_undoes_bury",
            q2 not in (-2, -3),
            f"undo_label_before={undo_before!r} queue_after={q2} undo_after={col.undo_status().undo!r}",
        )
        yield ("sleep", 1000)

        # A3: answer button click
        if mw.state != "review":
            yield ("hook", "reviewer_did_show_question", lambda: self.to_state("review"), HOOK_TIMEOUT)
        yield ("sleep", 800)
        if mw.reviewer.state != "answer":
            yield ("hook", "reviewer_did_show_answer", lambda: mw.reviewer.bottom.web.eval('pycmd("ans")'), HOOK_TIMEOUT)
        yield ("sleep", 1000)
        cid = mw.reviewer.card.id
        found = yield ("js", mw.reviewer.bottom.web, "!!document.querySelector('[data-ease=\"2\"]')")
        a = yield (
            "hook",
            "reviewer_did_answer_card",
            lambda: mw.reviewer.bottom.web.eval("document.querySelector('[data-ease=\"2\"]').click()"),
            HOOK_TIMEOUT,
        )
        ok = a is not None and a[2] == 2 and a[1].id == cid
        self.check(
            "A3.button_ease2_click",
            ok,
            {"button_found": found, "hook": None if a is None else {"card": a[1].id, "ease": a[2]}, "expected_card": cid},
        )
        yield ("sleep", 1200)

    # ------------------------------------------------- B (reviewer toggle)
    def reviewer_toggle(self) -> Generator:
        mw = _mw()
        ctx = self.ctx
        if mw.state != "review":
            yield ("hook", "reviewer_did_show_question", lambda: self.to_state("review"), HOOK_TIMEOUT)
        yield ("sleep", 800)
        if mw.reviewer.state != "answer":
            yield ("hook", "reviewer_did_show_answer", lambda: mw.reviewer._showAnswer(), HOOK_TIMEOUT)
        yield ("sleep", 1000)
        cid = mw.reviewer.card.id
        fired = {"q": 0}

        def on_q(card: Any) -> None:
            fired["q"] += 1

        gui_hooks.reviewer_did_show_question.append(on_q)
        try:
            cls_before = yield from self.classes()
            ctx.config.set("reviewer.ease_colors", False)
            yield ("sleep", 2000)
            cls_after = yield from self.classes()
            mw.grab().toImage().save(str(self.out / "B_reviewer_ease_colors_off.png"), "PNG")
            same = mw.reviewer.card is not None and mw.reviewer.card.id == cid
            self.check(
                "B.reviewer_toggle_no_rerender",
                mw.reviewer.state == "answer" and same and fired["q"] == 0,
                {
                    "state": mw.reviewer.state,
                    "same_card": same,
                    "question_hook_fires": fired["q"],
                    "classes_before": cls_before,
                    "classes_after": cls_after,
                },
            )
            ctx.config.set("reviewer.ease_colors", True)
            yield ("sleep", 1200)
            self.check("B.reviewer_toggle_back_still_answer", mw.reviewer.state == "answer" and mw.reviewer.card.id == cid)
        finally:
            try:
                gui_hooks.reviewer_did_show_question.remove(on_q)
            except Exception:
                pass
            try:
                ctx.config.reset()
            except Exception:
                pass

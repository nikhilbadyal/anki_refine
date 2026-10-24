"""Tools > Refine submenu."""

from __future__ import annotations

import json
from typing import Any, Dict

from aqt.qt import (
    QAction,
    QApplication,
    QDialog,
    QHBoxLayout,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

_refs: Dict[str, Any] = {}


def _report(ctx: Any) -> str:
    parts = []

    def safe(label: str, fn) -> None:
        try:
            parts.append("%s: %s" % (label, fn()))
        except Exception as exc:  # never fail the report
            parts.append("%s: <unavailable: %s>" % (label, exc))

    def anki_version():
        from anki.buildinfo import version

        return version

    def qt_version():
        from aqt.qt import qVersion

        return qVersion()

    def chromium():
        from aqt.qt import qWebEngineChromiumVersion

        return qWebEngineChromiumVersion()

    safe("Anki", anki_version)
    safe("Qt", qt_version)
    safe("Chromium", chromium)
    safe("Add-on package", lambda: ctx.addon_package)
    parts.append("")
    safe("Config", lambda: "\n" + json.dumps(ctx.config.get(), indent=2, sort_keys=True))
    parts.append("")

    def errors():
        errs = ctx.guard.errors()
        if not errs:
            return "none"
        return "\n" + "\n".join(
            "  %s: %d error(s); last:\n%s" % (k, len(v), v[-1] if v else "")
            for k, v in errs.items()
        )

    safe("Surface errors", errors)
    parts.append("")

    def tail():
        from ..log import recent

        return "\n" + (recent(ctx.user_files / "logs") or "(log is empty)")

    safe("Log", tail)
    return "\n".join(parts)


def _open_diagnostics(ctx: Any) -> None:
    try:
        old = _refs.get("diag")
        if old is not None:
            try:
                old.close()
                old.deleteLater()
            except Exception:
                pass
        dlg = QDialog(ctx.mw)
        dlg.setObjectName("RefineDiagnostics")
        dlg.setWindowTitle("Refine diagnostics")
        dlg.setModal(False)
        dlg.resize(640, 520)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)
        box = QPlainTextEdit()
        box.setReadOnly(True)
        box.setPlainText(_report(ctx))
        lay.addWidget(box)
        row = QHBoxLayout()
        copy = QPushButton("Copy report")
        copy.setAutoDefault(False)

        def do_copy() -> None:
            try:
                QApplication.clipboard().setText(box.toPlainText())
            except Exception:
                ctx.log.exception("copy failed")

        copy.clicked.connect(do_copy)
        close = QPushButton("Close")
        close.setDefault(True)
        close.clicked.connect(dlg.close)
        row.addWidget(copy)
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)
        _refs["diag"] = dlg
        dlg.show()
        dlg.raise_()
    except Exception:
        ctx.log.exception("could not open diagnostics")


def install_menu(ctx: Any) -> None:
    """Add Tools > Refine. Idempotent."""
    try:
        if _refs.get("menu") is not None and _refs.get("mw") is ctx.mw:
            return
        from .settings_dialog import open_settings

        parent = ctx.mw.form.menuTools
        menu = QMenu("Refine", parent)
        menu.setObjectName("RefineMenu")

        settings = QAction("Settings…", menu)
        settings.triggered.connect(lambda *_: open_settings(ctx))
        menu.addAction(settings)

        enabled = QAction("Enabled", menu)
        enabled.setCheckable(True)
        enabled.setChecked(bool(ctx.config.value("enabled")))

        def on_toggle(checked: bool) -> None:
            try:
                ctx.config.set("enabled", bool(checked))
            except Exception:
                ctx.log.exception("toggle failed")

        enabled.toggled.connect(on_toggle)
        menu.addAction(enabled)
        menu.addSeparator()

        diag = QAction("Diagnostics…", menu)
        diag.triggered.connect(lambda *_: _open_diagnostics(ctx))
        menu.addAction(diag)

        def on_config(cfg: dict, changed: frozenset) -> None:
            want = bool(cfg.get("enabled", True))
            if enabled.isChecked() != want:
                enabled.blockSignals(True)
                try:
                    enabled.setChecked(want)
                finally:
                    enabled.blockSignals(False)

        ctx.config.subscribe(on_config)
        parent.addMenu(menu)
        _refs.update(menu=menu, mw=ctx.mw, settings=settings, enabled=enabled, diag_action=diag)
    except Exception:
        ctx.log.exception("could not install Refine menu")

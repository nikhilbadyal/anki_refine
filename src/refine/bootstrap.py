"""Wires config, logging, the error guard and surfaces into Anki's hooks."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from . import log as logmod
from .config import ConfigStore
from .context import Context
from .guard import Guard
from .registry import Registry


def setup(mw: Any, module: str, addon_dir: Path) -> Context:
    started = time.perf_counter()
    logger = logmod.setup(addon_dir / "user_files" / "logs")
    am = mw.addonManager
    package = am.addonFromModule(module)
    am.setWebExports(module, r"web/.*\.(css|js|svg|woff2|png)$")

    store = ConfigStore(
        read=lambda: am.getConfig(module),
        write=lambda cfg: am.writeConfig(module, cfg),
    )
    registry_ref: dict[str, Registry] = {}

    def on_disable(surface_id: str, trace: str) -> None:
        logger.error("surface %s disabled after repeated errors:\n%s", surface_id, trace)
        reg = registry_ref.get("r")
        if reg is not None:
            reg.disable_after_errors(surface_id)

    guard = Guard(on_disable=on_disable)
    ctx = Context(
        mw=mw,
        config=store,
        guard=guard,
        log=logger,
        addon_package=package,
        addon_dir=addon_dir,
    )
    registry = Registry(ctx)
    registry_ref["r"] = registry

    def open_settings() -> None:
        from .ui.settings_dialog import open_settings as _open

        _open(ctx)

    am.setConfigAction(module, guard.wrap("core", open_settings))
    am.setConfigUpdatedAction(module, guard.wrap("core", lambda _conf: store.reload()))

    # Start now rather than at main_window_did_init: Anki loads add-ons
    # before it first draws the toolbar (finish_ui_setup) and before the
    # profile and deck list load, so the very first render is already styled
    # and nothing has to be redrawn.
    def start() -> None:
        registry.start()
        from .ui.menu import install_menu

        install_menu(ctx)

    guard.wrap("core", start)()
    store.subscribe(lambda cfg, changed: guard.wrap("core", registry.on_config)(cfg, changed))
    logger.info(
        "Refine %s loaded (package %s) in %.1f ms",
        _version(addon_dir),
        package,
        (time.perf_counter() - started) * 1000,
    )
    return ctx


def _version(addon_dir: Path) -> str:
    import json

    try:
        return json.loads((addon_dir / "manifest.json").read_text("utf-8")).get("human_version", "?")
    except Exception:
        return "?"

"""Surface protocol. One surface per area of Anki that Refine restyles."""

from __future__ import annotations

from typing import Any


class Surface:
    id: str = ""
    requires_hooks: tuple[str, ...] = ()

    def install(self, ctx: Any) -> None:
        """Register hooks. Called once from main_window_did_init."""

    def uninstall(self, ctx: Any) -> None:
        """Undo install(); called when the guard disables the surface."""

    def on_config(self, ctx: Any, cfg: dict, changed: frozenset) -> None:
        """React to settings changes (class flags are pushed by the registry)."""

    def flags(self, cfg: dict) -> dict[str, bool]:
        """Extra html classes this surface manages, beyond rf-s-<id>."""
        return {}

    def on_bridge(self, ctx: Any, cmd: str, context: Any) -> None:
        """Handle pycmd("refine:<id>:<cmd>") from our own markup."""


class WebSurface(Surface):
    # class names of the `context` objects passed to webview_will_set_content
    contexts: tuple[str, ...] = ()
    css: tuple[str, ...] = ()

    def contribute(self, ctx: Any, web_content: Any, context: Any, cfg: dict) -> None:
        """Add surface-specific markup; assets are added by the registry."""

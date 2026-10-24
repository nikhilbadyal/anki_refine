"""Refine's web assets, read once per session and inlined into pages.

Anki rebuilds a page on every screen change, and its media server tells the
webview not to cache add-on JS and to cache CSS for only 10 seconds
(aqt/mediasrv.py). Linking our files would therefore cost a round trip to
Anki's Python server per file on most screen changes (measured: +12
requests, ~40-50 ms on the deck list). Inlining them costs nothing at load
time. Fonts stay as files (cached for an hour by the same server); their
URLs are made absolute because inlined CSS resolves against the page URL.
"""

from __future__ import annotations

import re
from pathlib import Path

_cache: dict[str, str] = {}


def text(web_dir: Path, rel: str) -> str:
    if rel not in _cache:
        try:
            _cache[rel] = (web_dir / rel).read_text("utf-8")
        except OSError:
            _cache[rel] = ""
    return _cache[rel]


def css(web_dir: Path, web_base: str, files: list[str]) -> str:
    """One <style> block with the given css files (relative to web/css)."""
    parts = []
    for f in files:
        body = text(web_dir, f"css/{f}")
        # url("../fonts/x.woff2") -> url("/_addons/<pkg>/web/fonts/x.woff2")
        body = re.sub(r'url\("\.\./', f'url("{web_base}/', body)
        parts.append(body)
    return "<style data-refine>" + "\n".join(parts) + "</style>"


def script(web_dir: Path) -> str:
    return "<script data-refine>" + text(web_dir, "js/refine.js").replace("</", "<\\/") + "</script>"


def clear() -> None:
    _cache.clear()

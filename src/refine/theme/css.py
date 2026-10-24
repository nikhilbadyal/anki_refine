"""Web (CSS/JS) generation of the token block injected into Anki webviews."""

from __future__ import annotations

import json
from typing import Dict

from .tokens import tokens

STYLE_ID = "rf-tokens"


def _decls(tok: Dict[str, str]) -> str:
    parts = ["--rf-%s:%s;" % (k, v) for k, v in tok.items()]
    parts += [
        "--canvas:%s;" % tok["bg"],
        "--canvas-elevated:%s;" % tok["surface"],
        "--fg:%s;" % tok["text"],
        "--fg-subtle:%s;" % tok["text-muted"],
        "--border:%s;" % tok["border-strong"],
        "--border-subtle:%s;" % tok["border"],
    ]
    return "".join(parts)


def root_css(accent: str, density: str) -> str:
    light = _decls(tokens(False, accent, density))
    dark = _decls(tokens(True, accent, density))
    return ":root.refine{%s}\n:root.refine.night-mode{%s}" % (light, dark)


def style_tag(accent: str, density: str) -> str:
    return '<style id="%s">%s</style>' % (STYLE_ID, root_css(accent, density))


def live_update_js(accent: str, density: str) -> str:
    css = json.dumps(root_css(accent, density)).replace("</", "<\\/")
    return (
        "(function(){var s=document.getElementById(%s);"
        "if(!s){s=document.createElement('style');s.id=%s;"
        "(document.head||document.documentElement).appendChild(s);}"
        "s.textContent=%s;})();"
    ) % (json.dumps(STYLE_ID), json.dumps(STYLE_ID), css)

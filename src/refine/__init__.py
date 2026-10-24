"""Refine: a modern look for Anki Desktop.

M0 skeleton. It only registers the add-on's web exports so the dev tooling
can confirm assets are served under /_addons/<package>/web/. No hooks, no
styling. Surfaces arrive in M1+ (see PLAN.md section 9).
"""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

try:
    from aqt import mw

    if mw is not None:
        mw.addonManager.setWebExports(__name__, r"web/.*\.(css|js|svg|woff2)$")
except Exception:  # never let start-up problems reach Anki's error dialog
    _log.exception("Refine failed to initialise; Anki will run without it.")

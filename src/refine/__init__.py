"""Refine: a modern look for Anki Desktop.

Entry point. Everything is set up by bootstrap.setup(); any failure there is
logged and Anki continues with its stock interface. `_ctx` is exposed for the
dev-only screenshot probe.
"""

from __future__ import annotations

import logging
from pathlib import Path

_log = logging.getLogger("refine")
_ctx = None

try:
    from aqt import mw
except ImportError:  # imported outside Anki, e.g. by unit tests
    mw = None

if mw is not None:
    try:
        from .bootstrap import setup

        _ctx = setup(mw, __name__, Path(__file__).resolve().parent)
    except Exception:  # never let start-up problems reach Anki's error dialog
        _log.exception("Refine failed to initialise; Anki will run without it.")

"""Logging setup for the add-on (rotating file in user_files, never stderr)."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

_NAME = "refine"
_FILE = "refine.log"


def setup(log_dir: Optional[Path]) -> logging.Logger:
    logger = logging.getLogger(_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass
    handler: logging.Handler
    try:
        if log_dir is None:
            raise ValueError("no log dir")
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            str(log_dir / _FILE), maxBytes=256 * 1024, backupCount=2, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    except Exception:
        handler = logging.NullHandler()
    logger.addHandler(handler)
    return logger


def recent(log_dir: Path, lines: int = 200) -> str:
    try:
        text = (Path(log_dir) / _FILE).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return "\n".join(text.splitlines()[-lines:])

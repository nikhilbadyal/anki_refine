"""Logging setup for the add-on (rotating file in user_files, never stderr).

The log file is opened only while a line is written. Anki updates an add-on by
renaming its user_files folder, which Windows refuses while any file inside is
open, so a handler that keeps the file open would make every update fail."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

_NAME = "refine"
_FILE = "refine.log"


class _ClosingFileHandler(RotatingFileHandler):
    """RotatingFileHandler that closes the file after each record."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, delay=True, **kwargs)

    def handleError(self, record: logging.LogRecord) -> None:
        pass  # a failed log write (e.g. the folder is mid-update) must not bother Anki

    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        finally:
            self.acquire()
            try:
                if self.stream is not None:
                    try:
                        self.stream.close()
                    finally:
                        self.stream = None
            except Exception:
                pass
            finally:
                self.release()


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
        handler = _ClosingFileHandler(
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

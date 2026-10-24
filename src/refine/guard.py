"""Error containment: wrap callbacks so a failure never reaches Anki."""

from __future__ import annotations

import functools
import logging
import traceback
from typing import Any, Callable, Dict, List, Optional, Set

_MAX_KEPT = 10


class Guard:
    def __init__(self, on_disable: Callable[[str, str], None], limit: int = 3) -> None:
        self._on_disable = on_disable
        self._limit = limit
        self._counts: Dict[str, int] = {}
        self._errors: Dict[str, List[str]] = {}
        self._disabled: Set[str] = set()

    def wrap(self, surface_id: str, fn: Callable, *, is_filter: bool = False) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kw: Any) -> Any:
            fallback = args[0] if (is_filter and args) else None
            if surface_id in self._disabled:
                return fallback
            try:
                return fn(*args, **kw)
            except Exception:
                try:
                    self._record(surface_id)
                except Exception:
                    pass
                return fallback

        wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
        return wrapper

    def _record(self, surface_id: str) -> None:
        tb = traceback.format_exc()
        logging.getLogger("refine").error("Error in surface %r:\n%s", surface_id, tb)
        errs = self._errors.setdefault(surface_id, [])
        errs.append(tb)
        del errs[:-_MAX_KEPT]
        n = self._counts.get(surface_id, 0) + 1
        self._counts[surface_id] = n
        if n >= self._limit and surface_id not in self._disabled:
            self._disabled.add(surface_id)
            try:
                self._on_disable(surface_id, tb)
            except Exception:
                logging.getLogger("refine").exception("on_disable failed")

    def is_disabled(self, surface_id: str) -> bool:
        return surface_id in self._disabled

    def errors(self) -> Dict[str, List[str]]:
        return {k: list(v) for k, v in self._errors.items()}

    def reset(self, surface_id: Optional[str] = None) -> None:
        if surface_id is None:
            self._counts.clear()
            self._errors.clear()
            self._disabled.clear()
        else:
            self._counts.pop(surface_id, None)
            self._errors.pop(surface_id, None)
            self._disabled.discard(surface_id)

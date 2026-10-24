"""Configuration schema, normalisation and a small observable store."""

from __future__ import annotations

import copy
import logging
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional

from .theme.palettes import ACCENTS

SCHEMA_VERSION = 1
ACCENT_IDS = tuple(ACCENTS.keys())
DENSITIES = ("comfortable", "compact")
SURFACE_IDS = ("toolbar", "deck_browser", "overview", "reviewer", "qt_chrome", "pages")

HOME_IDS = ("hero", "today", "activity", "forecast")
# opt-in card-content layer; off by default because it touches card rendering
CARD_IDS = ("japanese", "furigana_hover")
MAX_DAILY_GOAL = 5000

DEFAULTS: Dict[str, Any] = {
    "schema_version": 1,
    "enabled": True,
    "accent": "jade",
    "density": "comfortable",
    "surfaces": {s: True for s in SURFACE_IDS},
    "reviewer": {"ease_colors": True},
    "home": {k: True for k in HOME_IDS},
    "cards": {k: False for k in CARD_IDS},
    # cards per day for the Today panel; 0 = no goal
    "daily_goal": 0,
}

_log = logging.getLogger("refine")


def _migrate(raw: Dict[str, Any]) -> Dict[str, Any]:
    # No older schemas exist yet; this is the hook for future migrations.
    return raw


def normalize(raw: Optional[Mapping]) -> Dict[str, Any]:
    out = copy.deepcopy(DEFAULTS)
    try:
        if not isinstance(raw, Mapping):
            return out
        raw = _migrate(dict(raw))
        if isinstance(raw.get("enabled"), bool):
            out["enabled"] = raw["enabled"]
        if isinstance(raw.get("accent"), str) and raw["accent"] in ACCENT_IDS:
            out["accent"] = raw["accent"]
        if isinstance(raw.get("density"), str) and raw["density"] in DENSITIES:
            out["density"] = raw["density"]
        surfaces = raw.get("surfaces")
        if isinstance(surfaces, Mapping):
            for s in SURFACE_IDS:
                if isinstance(surfaces.get(s), bool):
                    out["surfaces"][s] = surfaces[s]
        home = raw.get("home")
        if isinstance(home, Mapping):
            for h in HOME_IDS:
                if isinstance(home.get(h), bool):
                    out["home"][h] = home[h]
        goal = raw.get("daily_goal")
        if isinstance(goal, int) and not isinstance(goal, bool) and 0 <= goal <= MAX_DAILY_GOAL:
            out["daily_goal"] = goal
        cards = raw.get("cards")
        if isinstance(cards, Mapping):
            for c in CARD_IDS:
                if isinstance(cards.get(c), bool):
                    out["cards"][c] = cards[c]
        reviewer = raw.get("reviewer")
        if isinstance(reviewer, Mapping) and isinstance(reviewer.get("ease_colors"), bool):
            out["reviewer"]["ease_colors"] = reviewer["ease_colors"]
    except Exception:
        _log.exception("config normalize failed; using defaults")
        return copy.deepcopy(DEFAULTS)
    out["schema_version"] = SCHEMA_VERSION
    return out


def _flatten(d: Mapping, prefix: str = "") -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, Mapping):
            flat.update(_flatten(v, prefix + k + "."))
        else:
            flat[prefix + k] = v
    return flat


def _set_path(d: Dict[str, Any], path: str, value: Any) -> None:
    keys = path.split(".")
    cur = d
    for k in keys[:-1]:
        nxt = cur.get(k)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[k] = nxt
        cur = nxt
    cur[keys[-1]] = value


class ConfigStore:
    def __init__(
        self,
        read: Callable[[], Optional[Mapping]],
        write: Callable[[dict], None],
    ) -> None:
        self._read = read
        self._write = write
        self._subs: List[Callable[[dict, FrozenSet[str]], None]] = []
        self._cfg = self._load()

    def _load(self) -> Dict[str, Any]:
        try:
            return normalize(self._read())
        except Exception:
            _log.exception("config read failed; using defaults")
            return normalize(None)

    def get(self) -> dict:
        return copy.deepcopy(self._cfg)

    def value(self, path: str) -> Any:
        cur: Any = self._cfg
        for k in path.split("."):
            if not isinstance(cur, Mapping) or k not in cur:
                return None
            cur = cur[k]
        return copy.deepcopy(cur)

    def set(self, path: str, value: Any) -> None:
        self.update({path: value})

    def update(self, changes: Mapping[str, Any]) -> None:
        raw = copy.deepcopy(self._cfg)
        for path, value in changes.items():
            _set_path(raw, path, value)
        self._apply(normalize(raw), persist=True)

    def reset(self) -> None:
        self._apply(normalize(None), persist=True)

    def reload(self) -> None:
        self._apply(self._load(), persist=False)

    def subscribe(self, fn: Callable[[dict, FrozenSet[str]], None]) -> None:
        self._subs.append(fn)

    def _apply(self, new: Dict[str, Any], persist: bool) -> None:
        old_flat = _flatten(self._cfg)
        new_flat = _flatten(new)
        changed = frozenset(
            k for k in set(old_flat) | set(new_flat) if old_flat.get(k) != new_flat.get(k)
        )
        self._cfg = new
        if persist:
            try:
                self._write(copy.deepcopy(new))
            except Exception:
                _log.exception("config write failed")
        if not changed:
            return
        for fn in list(self._subs):
            try:
                fn(copy.deepcopy(new), changed)
            except Exception:
                _log.exception("config subscriber failed")

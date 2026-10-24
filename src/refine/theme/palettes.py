"""Base palettes: neutrals per theme and the selectable accent colours."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Accent:
    id: str
    label: str
    light: str
    dark: str


ACCENTS: Dict[str, Accent] = {
    a.id: a
    for a in (
        Accent("jade", "Jade", "#1E8466", "#5FCFA6"),
        Accent("blue", "Blue", "#2F6FEB", "#6EA8FE"),
        Accent("indigo", "Indigo", "#5B5BD6", "#8B8DF8"),
        Accent("violet", "Violet", "#7C4DDB", "#B197FC"),
        Accent("rose", "Rose", "#D6336C", "#F77FA6"),
        Accent("amber", "Amber", "#AB640D", "#F2B33D"),
        Accent("teal", "Teal", "#0E7C86", "#4FC3CF"),
        Accent("graphite", "Graphite", "#3F3F46", "#D4D4D8"),
    )
}

NEUTRAL_LIGHT: Dict[str, str] = {
    "bg": "#F6F5F2",
    "surface": "#FFFFFF",
    "surface-hover": "#F1F0EC",
    "surface-active": "#E9E7E2",
    "surface-sunken": "#EFEDE8",
    "border": "rgba(0, 0, 0, 0.07)",
    "border-strong": "rgba(0, 0, 0, 0.14)",
    "text": "#1C1B19",
    # muted/faint both meet WCAG AA (4.5:1) on every surface they sit on
    "text-muted": "#57544E",
    "text-faint": "#67645E",
    "overlay": "rgba(0, 0, 0, 0.035)",
}

NEUTRAL_DARK: Dict[str, str] = {
    "bg": "#1A1918",
    "surface": "#222120",
    "surface-hover": "#2A2927",
    "surface-active": "#31302D",
    "surface-sunken": "#151413",
    "border": "rgba(255, 255, 255, 0.06)",
    "border-strong": "rgba(255, 255, 255, 0.12)",
    "text": "#ECEBE7",
    "text-muted": "#B5B2A9",
    "text-faint": "#9B9890",
    "overlay": "rgba(255, 255, 255, 0.04)",
}

# State colours (text-usable)
STATE_LIGHT: Dict[str, str] = {
    "new": "#2F6BD8", "learn": "#C24A33", "review": "#1E8654",
    "again": "#C24A33", "hard": "#A86A12", "good": "#1E8654", "easy": "#2F6BD8",
}
STATE_DARK: Dict[str, str] = {
    "new": "#7AA9F5", "learn": "#F08A7A", "review": "#6FD3A0",
    "again": "#F08A7A", "hard": "#E8B04A", "good": "#6FD3A0", "easy": "#7AA9F5",
}

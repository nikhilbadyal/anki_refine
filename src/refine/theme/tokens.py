"""Design tokens: resolved colour and metric values per theme/accent/density."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .palettes import (
    ACCENTS,
    NEUTRAL_DARK,
    NEUTRAL_LIGHT,
    STATE_DARK,
    STATE_LIGHT,
)

DEFAULT_ACCENT = "jade"
DEFAULT_DENSITY = "comfortable"
_DENSITIES = ("comfortable", "compact")

CONTRAST_RULES: List[Tuple[str, str, float]] = [
    ("text", "bg", 4.5),
    ("text", "surface", 4.5),
    ("text-muted", "bg", 4.5),
    ("text-muted", "surface", 4.5),
    ("accent-fg", "accent", 4.5),
    ("accent-text", "surface", 4.5),
    ("accent", "surface", 3.0),
    ("focus", "bg", 3.0),
    ("new", "surface", 4.5),
    ("learn", "surface", 4.5),
    ("review", "surface", 4.5),
    ("again", "surface", 3.0),
    ("hard", "surface", 3.0),
    ("good", "surface", 3.0),
    ("easy", "surface", 3.0),
    # faint text carries content (column headers, notes, key hints): AA, on
    # every surface it appears on
    ("text-faint", "surface", 4.5),
    ("text-faint", "bg", 4.5),
    ("text-faint", "surface-sunken", 4.5),
    ("text-faint", "surface-hover", 4.5),
    ("text-muted", "surface-active", 4.5),
    ("muted-count", "surface", 4.5),
    ("primary-fg", "primary-bg", 4.5),
]

# ---- colour helpers (private) -------------------------------------------


def _parse(value: str) -> Tuple[float, float, float, float]:
    """Parse #RGB, #RRGGBB or rgb()/rgba() into (r, g, b, a), rgb in 0-255."""
    v = value.strip()
    if v.startswith("#"):
        h = v[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) != 6:
            raise ValueError("bad colour: %r" % value)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    if v.lower().startswith("rgb"):
        inner = v[v.index("(") + 1: v.rindex(")")]
        parts = [p.strip() for p in inner.split(",")]
        a = float(parts[3]) if len(parts) > 3 else 1.0
        return (float(parts[0]), float(parts[1]), float(parts[2]), a)
    raise ValueError("bad colour: %r" % value)


def _hex(rgb: Tuple[float, float, float]) -> str:
    r, g, b = (max(0, min(255, int(round(c)))) for c in rgb)
    return "#%02X%02X%02X" % (r, g, b)


def _mix(a: str, b: str, t: float) -> str:
    """Linear mix: t=0 -> a, t=1 -> b (opaque result)."""
    ra, ga, ba, _ = _parse(a)
    rb, gb, bb, _ = _parse(b)
    return _hex((ra + (rb - ra) * t, ga + (gb - ga) * t, ba + (bb - ba) * t))


def _lighten(color: str, amount: float) -> str:
    return _mix(color, "#FFFFFF", amount)


def _darken(color: str, amount: float) -> str:
    return _mix(color, "#000000", amount)


def _num(x: float) -> str:
    s = ("%.2f" % x).rstrip("0").rstrip(".")
    return s or "0"


def _rgba(color: str, alpha: float) -> str:
    r, g, b, _ = _parse(color)
    return "rgba(%d, %d, %d, %s)" % (int(round(r)), int(round(g)), int(round(b)), _num(alpha))


def _lin(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(rgb: Tuple[float, float, float]) -> float:
    r, g, b = rgb
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(fg: str, bg: str) -> float:
    """WCAG 2.x contrast ratio. Translucent colours are composited (bg over white)."""
    br, bgc, bb, ba = _parse(bg)
    if ba < 1.0:
        br, bgc, bb = (c * ba + 255 * (1 - ba) for c in (br, bgc, bb))
    fr, fgc, fb, fa = _parse(fg)
    if fa < 1.0:
        fr, fgc, fb = (c * fa + o * (1 - fa) for c, o in ((fr, br), (fgc, bgc), (fb, bb)))
    l1 = _luminance((fr, fgc, fb))
    l2 = _luminance((br, bgc, bb))
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _accent_fg(accent: str) -> str:
    white, ink = "#FFFFFF", "#111113"
    return white if contrast(white, accent) >= contrast(ink, accent) else ink


def _accent_text(accent: str, surface: str, night: bool) -> str:
    color = accent
    for _ in range(40):
        if contrast(color, surface) >= 4.5:
            break
        color = _lighten(color, 0.05) if night else _darken(color, 0.05)
    return color


# ---- public ---------------------------------------------------------------


def tokens(night: bool, accent: str, density: str) -> Dict[str, str]:
    if accent not in ACCENTS:
        accent = DEFAULT_ACCENT
    if density not in _DENSITIES:
        density = DEFAULT_DENSITY
    night = bool(night)

    neutral = NEUTRAL_DARK if night else NEUTRAL_LIGHT
    state = STATE_DARK if night else STATE_LIGHT
    base = ACCENTS[accent].dark if night else ACCENTS[accent].light
    soft_a = 0.16 if night else 0.12

    t: Dict[str, str] = dict(neutral)
    t["accent"] = base
    t["accent-hover"] = _lighten(base, 0.08) if night else _darken(base, 0.08)
    t["accent-fg"] = _accent_fg(base)
    t["accent-soft"] = _rgba(base, soft_a)
    t["accent-text"] = _accent_text(base, t["surface"], night)
    t["focus"] = base if contrast(base, t["bg"]) >= 3.0 else t["accent-text"]
    t.update(state)
    if night:
        t.update({"primary-bg": "#ECEBE7", "primary-fg": "#161514",
                  "primary-hover": "#FFFFFF", "muted-count": "#9B9890"})
    else:
        t.update({"primary-bg": "#1C1B19", "primary-fg": "#FFFFFF",
                  "primary-hover": "#000000", "muted-count": "#67645E"})
    for k in ("again", "hard", "good", "easy"):
        t[k + "-soft"] = _rgba(t[k], soft_a)
    if night:
        t["shadow-1"] = "0 1px 2px rgba(0, 0, 0, 0.5)"
        t["shadow-2"] = "0 8px 24px rgba(0, 0, 0, 0.5)"
    else:
        t["shadow-1"] = "0 1px 2px rgba(0, 0, 0, 0.06)"
        t["shadow-2"] = "0 4px 16px rgba(0, 0, 0, 0.08)"

    for i, px in enumerate([4, 8, 12, 16, 24, 32], start=1):
        if density == "compact" and i >= 2:
            px = int(round(px * 0.75))
        t["space-%d" % i] = "%dpx" % px
    t["row-pad"] = "5px" if density == "compact" else "8px"
    t["radius-s"] = "7px"
    t["radius-m"] = "10px"
    t["radius-l"] = "14px"
    t["font-ui"] = "'Hanken Grotesk', system-ui, -apple-system, 'Segoe UI', sans-serif"
    t["font-display"] = "'Newsreader', Georgia, 'Times New Roman', serif"
    t["font-mono"] = "'JetBrains Mono', ui-monospace, Consolas, monospace"
    t["font-jp"] = "'Noto Serif JP', 'Yu Mincho', 'Hiragino Mincho ProN', serif"
    t["text-xs"] = "12px"
    t["text-s"] = "13px"
    t["text-m"] = "14px"
    t["text-l"] = "16px"
    t["text-xl"] = "20px"
    t["text-2xl"] = "24px"
    t["text-3xl"] = "30px"
    t["text-hero"] = "46px"
    t["dur"] = "140ms"
    t["ease"] = "cubic-bezier(.2,0,0,1)"
    return t

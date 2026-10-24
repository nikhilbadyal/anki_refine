# Module interfaces (M1–M4)

Binding contract between modules. Code against these signatures exactly. Background: [PLAN.md](../PLAN.md) §6 (design system), §7 (architecture); [M0-REPORT.md](M0-REPORT.md) (verified Anki behaviour).

## Global rules

- Package: `src/refine/` (Python package name at runtime is the add-on folder name, which is `refine` in dev and a numeric AnkiWeb id when installed, so **only relative imports inside the package**: `from .config import ConfigStore`, `from ..theme import tokens`).
- Python 3.9-compatible syntax: `from __future__ import annotations` at the top of every module; no `match`; no `X | Y` outside annotations; no `dict[str, int]` in runtime expressions (fine in annotations).
- **Pure modules** (`config.py`, `guard.py`, `log.py`, `theme/*`) must not import `aqt`, `anki`, or Qt. They are unit-tested with plain `py -3.11 -m unittest discover -s tests -t .` without Anki.
- Qt imports only via `from aqt.qt import ...` (never `PyQt6` directly).
- Never `print` to stderr; never `assert` for runtime checks (stripped in release builds).
- Tests live in `tests/unit/test_<module>.py`, use `unittest` only (no pytest), and add `sys.path.insert(0, str(ROOT / "src"))` then `import refine.<module>`. Importing `refine` executes `src/refine/__init__.py`; it **must** be safe when `aqt` is not importable (wrap aqt imports in try/except ImportError).

## `refine/config.py` (pure)

```python
SCHEMA_VERSION: int = 1
ACCENT_IDS: tuple[str, ...]          # same ids as theme.palettes.ACCENTS
DENSITIES: tuple[str, ...] = ("comfortable", "compact")
SURFACE_IDS: tuple[str, ...] = ("toolbar", "deck_browser", "overview", "reviewer", "qt_chrome")

DEFAULTS: dict = {
    "schema_version": 1,
    "enabled": True,
    "accent": "jade",
    "density": "comfortable",
    "surfaces": {"toolbar": True, "deck_browser": True, "overview": True,
                 "reviewer": True, "qt_chrome": True},
    "reviewer": {"ease_colors": True},
    "home": {"hero": True, "today": True, "activity": True, "forecast": True},
}
# Design source: user's Claude Design project "Anki UI revamp discussion" (Anki Revamp.dc.html):
# warm near-black neutrals, jade accent, inverted primary buttons (primary-bg/primary-fg tokens),
# Hanken Grotesk / Newsreader / JetBrains Mono. Accent ids: jade, blue, indigo, violet, rose,
# amber, teal, graphite. Extra token keys: primary-bg, primary-fg, primary-hover, muted-count,
# font-display, font-jp, text-3xl, text-hero.

def normalize(raw: Mapping | None) -> dict
    """Deep-merge raw over DEFAULTS, drop unknown keys, coerce/replace invalid values
    with defaults (wrong type, unknown accent/density), run migrations for older
    schema_version, always return a fresh dict with schema_version == SCHEMA_VERSION.
    Never raises."""

class ConfigStore:
    def __init__(self, read: Callable[[], Mapping | None], write: Callable[[dict], None]) -> None
    def get(self) -> dict                         # normalized copy (callers may not mutate store)
    def value(self, path: str) -> Any             # dotted path, e.g. "surfaces.toolbar"
    def set(self, path: str, value: Any) -> None  # validate via normalize; write; notify if changed
    def update(self, changes: Mapping[str, Any]) -> None  # several dotted paths, one write/notify
    def reset(self) -> None                       # DEFAULTS; write; notify
    def reload(self) -> None                      # re-read (e.g. after Anki's JSON config editor saved)
    def subscribe(self, fn: Callable[[dict, frozenset[str]], None]) -> None
        # fn(new_config, changed_dotted_paths); exceptions in fn are swallowed (logged via logging)
```
Write failures are logged and swallowed; the in-memory config stays updated.

## `refine/guard.py` (pure)

```python
class Guard:
    def __init__(self, on_disable: Callable[[str, str], None], limit: int = 3) -> None
        # on_disable(surface_id, last_traceback_text) is called ONCE when a surface's
        # error count reaches `limit` within this session.
    def wrap(self, surface_id: str, fn: Callable, *, is_filter: bool = False) -> Callable
        # returns wrapper(*args, **kw). On exception: log (logging.getLogger("refine")),
        # count, maybe on_disable; return args[0] if is_filter else None. Never raises.
        # wrapper.__wrapped__ = fn. If the surface is already disabled the wrapper is a
        # passthrough no-op (returns args[0] for filters).
    def is_disabled(self, surface_id: str) -> bool
    def errors(self) -> dict[str, list[str]]   # surface_id -> traceback texts (max 10 each)
    def reset(self, surface_id: str | None = None) -> None
```

## `refine/log.py` (pure)

```python
def setup(log_dir: Path | None) -> logging.Logger
    # logger "refine", level INFO, propagate=False, RotatingFileHandler(log_dir/"refine.log",
    # 256 KiB, 2 backups, utf-8) when log_dir is given and creatable; otherwise NullHandler.
    # Idempotent (no duplicate handlers on repeated calls).
def recent(log_dir: Path, lines: int = 200) -> str   # tail of refine.log, "" if missing
```

## `refine/theme/palettes.py` (pure)

```python
@dataclass(frozen=True)
class Accent:
    id: str; label: str; light: str; dark: str   # hex "#RRGGBB" base accent per theme
ACCENTS: dict[str, Accent]   # ordered: indigo, blue, teal, green, amber, rose, violet, graphite
NEUTRAL_LIGHT: dict[str, str]; NEUTRAL_DARK: dict[str, str]   # see token table below
```

## `refine/theme/tokens.py` (pure)

```python
def tokens(night: bool, accent: str, density: str) -> dict[str, str]
    # keys WITHOUT the "--rf-" prefix. Colour keys (all "#RRGGBB" or "rgba(r, g, b, a)"):
    #   bg, surface, surface-hover, surface-active, surface-sunken, border, border-strong,
    #   text, text-muted, text-faint, accent, accent-hover, accent-fg, accent-soft,
    #   accent-text (accent usable as text on surface), focus,
    #   new, learn, review, again, hard, good, easy,
    #   again-soft, hard-soft, good-soft, easy-soft, shadow-1, shadow-2, overlay
    # Non-colour keys (theme independent except shadows):
    #   radius-s "6px", radius-m "10px", radius-l "14px",
    #   space-1 "4px" … space-6 "32px" (comfortable) — compact multiplies space-2..space-6 by 0.75 (rounded to int px),
    #   row-pad (deck row vertical padding: "8px" comfortable / "5px" compact),
    #   font-ui (system stack), font-mono, text-xs "12px", text-s "13px", text-m "14px", text-l "16px",
    #   text-xl "20px", text-2xl "24px", dur "140ms", ease "cubic-bezier(.2,0,0,1)"
def contrast(fg: str, bg: str) -> float        # WCAG 2.x ratio; accepts #RGB/#RRGGBB; rgba composited over bg
CONTRAST_RULES: list[tuple[str, str, float]]   # (fg_key, bg_key, minimum) checked by tests:
    # text/bg 4.5, text/surface 4.5, text-muted/bg 4.5, text-muted/surface 4.5,
    # accent-fg/accent 4.5, accent-text/surface 4.5, accent/surface 3.0, focus/bg 3.0,
    # new/surface 4.5, learn/surface 4.5, review/surface 4.5,
    # again/surface 3.0, hard/surface 3.0, good/surface 3.0, easy/surface 3.0, text-faint/surface 3.0
```
`accent-fg` is computed (white or near-black, whichever passes). `accent-text` is the accent darkened (light) / lightened (dark) until it passes 4.5 on surface. Fallback for unknown accent/density: defaults.

## `refine/theme/css.py` (pure)

```python
def root_css(accent: str, density: str) -> str
    # ":root.refine{--rf-…:…;}\n:root.refine.night-mode{--rf-…:…;}" — both themes in one block,
    # because Anki flips html.night-mode without re-rendering (M0 F2). Also maps a few Anki
    # tokens for blending: inside :root.refine set --canvas, --canvas-elevated, --fg,
    # --fg-subtle, --border, --border-subtle from our tokens.
STYLE_ID = "rf-tokens"
def style_tag(accent: str, density: str) -> str   # f'<style id="{STYLE_ID}">…</style>'
def live_update_js(accent: str, density: str) -> str
    # JS that creates/replaces <style id="rf-tokens"> in the current document (JSON-escaped)
```

## `refine/theme/qss.py` (pure)

```python
MARK_BEGIN = "/* refine:begin */"; MARK_END = "/* refine:end */"
def render(tok: dict[str, str]) -> str
    # QSS for: QMenuBar, QMenuBar::item(:selected), QMenu (padding, border, radius),
    # QMenu::item(:selected/:disabled), QMenu::separator, QToolTip, QScrollBar (vertical &
    # horizontal: thin track, rounded handle, hover; hide add-line/sub-line arrows),
    # focus outline colour for QLineEdit/QComboBox/QSpinBox/QTextEdit:focus.
    # Uses only tok colour values (QSS has no variables). Wrapped in MARK_BEGIN/MARK_END.
def splice(stylesheet: str, block: str) -> str  # replace existing marked block or append
def strip(stylesheet: str) -> str               # remove marked block (idempotent)
```

## `refine/surfaces/base.py` (aqt allowed; owned by lead)

```python
class Surface:
    id: str                        # one of config.SURFACE_IDS
    requires_hooks: tuple[str, ...]
    def install(self, ctx: Context) -> None
    def uninstall(self, ctx: Context) -> None
    def on_config(self, ctx: Context, cfg: dict, changed: frozenset[str]) -> None
```
`Context` (in `refine/context.py`): `.mw`, `.config: ConfigStore`, `.guard: Guard`, `.log`, `.addon_package: str`, `.web_base: str` (= f"/_addons/{addon_package}/web"), `.addon_dir: Path`.

## `refine/ui/settings_dialog.py` (aqt allowed)

```python
def open_settings(ctx: Context) -> None     # non-modal singleton QDialog, parent ctx.mw
```
Sections: Appearance (accent swatches as a row of round colour buttons with accessible names + selected state; density radio), Screens (checkbox per surface with one-line description), Reviewer (ease colours checkbox), footer: "Reset to defaults" (confirm via aqt.utils.askUser), "Open log folder", Close. Every control writes immediately through `ctx.config.set/update` (live apply). Reflects external config changes via `ctx.config.subscribe`. Keyboard: all controls reachable by Tab, Esc closes. Object name `RefineSettings`.

## `refine/ui/menu.py`

```python
def install_menu(ctx: Context) -> None   # Tools ▸ Refine ▸ {Settings…, Disable for this session / Enable, Diagnostics… (log tail in a read-only dialog)}
```

"""Non-modal settings dialog. Every control writes through ctx.config immediately."""

from __future__ import annotations

from typing import Any, Dict, Optional

from aqt.qt import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFont,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QSize,
    QToolButton,
    Qt,
    QVBoxLayout,
    QWidget,
)

from ..config import DENSITIES, MAX_DAILY_GOAL, SURFACE_IDS
from ..theme.palettes import ACCENTS

_dialog: Optional["_SettingsDialog"] = None
_subscribed_configs: list = []  # config stores we already subscribed to

_SURFACES = {
    "toolbar": ("Top toolbar", "Decks, Add, Browse, Stats, Sync"),
    "deck_browser": ("Deck list", "Rows, counts and actions on the home screen"),
    "overview": ("Deck overview", "Study screen for a single deck"),
    "reviewer": (
        "Reviewer controls",
        "Answer buttons and bottom bar — card content is never changed",
    ),
    "qt_chrome": ("Menus and scrollbars", "Application menus, tooltips and scrollbars"),
    "pages": ("Statistics and deck options", "Colours and fonts only; these screens keep Anki's layout"),
    "sidebar": ("Sidebar navigation", "Left sidebar on Home, Overview and Stats; Stats opens in the main window"),
}
_HOME = (
    ("hero", "Cards-waiting headline"),
    ("today", "Today panel"),
    ("activity", "Activity heatmap"),
    ("forecast", "Next 7 days forecast"),
    ("progress", "New cards progress"),
    ("leeches", "Leech warnings"),
)
_DENSITY_LABELS ={"comfortable": "Comfortable", "compact": "Compact"}


def _night() -> bool:
    try:
        from aqt import theme

        return bool(theme.theme_manager.night_mode)
    except Exception:
        return False


def _swatch_style(color: str) -> str:
    return (
        "QToolButton{background:%s;border:2px solid transparent;border-radius:14px;}"
        "QToolButton:hover{border:2px solid palette(mid);}"
        "QToolButton:focus{border:2px solid palette(highlight);}"
        "QToolButton:checked{border:2px solid palette(text);}" % color
    )


def _muted(label: QLabel) -> QLabel:
    label.setStyleSheet("color: palette(placeholder-text);")
    label.setWordWrap(True)
    return label


class _SettingsDialog(QDialog):
    def __init__(self, ctx: Any) -> None:
        super().__init__(ctx.mw)
        self.ctx = ctx
        self.setObjectName("RefineSettings")
        self.setWindowTitle("Refine")
        self.setMinimumWidth(520)
        self.setModal(False)
        self._syncing = False
        self._swatches: Dict[str, QToolButton] = {}
        self._density: Dict[str, QRadioButton] = {}
        self._surface: Dict[str, QCheckBox] = {}
        self._home: Dict[str, QCheckBox] = {}
        self._build()
        self.sync(self.ctx.config.get())
        self._fit_to_screen()

    def _fit_to_screen(self) -> None:
        try:
            screen = self.screen() or self.ctx.mw.screen()
            avail = screen.availableGeometry().height()
            want = self._body.sizeHint().height() + 72  # footer + rule
            self.resize(max(self.minimumWidth(), 560), min(want, int(avail * 0.85)))
        except Exception:
            self.ctx.log.exception("settings sizing failed")

    # -- helpers -------------------------------------------------------
    def _safe(self, fn):
        def wrapper(*args):
            try:
                if not self._syncing:
                    fn(*args)
            except Exception:
                self.ctx.log.exception("settings handler failed")

        return wrapper

    def _section(self, text: str) -> QLabel:
        lab = QLabel(text.upper())
        lab.setObjectName("RefineSection")
        f = lab.font()
        f.setPixelSize(11)
        f.setBold(True)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
        lab.setFont(f)
        lab.setStyleSheet("color: palette(placeholder-text);")
        return lab

    def _rule(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setStyleSheet("color: palette(midlight);")
        return line

    def _row_label(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setMinimumWidth(72)
        return lab

    # -- build ---------------------------------------------------------
    def _build(self) -> None:
        # Sections scroll; the footer stays visible. Keeps the dialog usable
        # on short screens (e.g. 1366x768 laptops at 125% scaling).
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QWidget()
        root = QVBoxLayout(body)
        root.setContentsMargins(20, 20, 20, 12)
        root.setSpacing(14)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        self._body = body

        title = QLabel("Refine")
        tf = title.font()
        tf.setPixelSize(16)
        tf.setWeight(QFont.Weight.DemiBold)
        title.setFont(tf)
        sub = _muted(QLabel("Changes apply immediately."))
        head = QVBoxLayout()
        head.setSpacing(2)
        head.addWidget(title)
        head.addWidget(sub)
        root.addLayout(head)
        root.addWidget(self._rule())

        # Appearance
        root.addWidget(self._section("Appearance"))
        night = _night()
        accent_row = QHBoxLayout()
        accent_row.setSpacing(8)
        accent_row.addWidget(self._row_label("Accent"))
        self._accent_group = QButtonGroup(self)
        self._accent_group.setExclusive(True)
        for aid, acc in ACCENTS.items():
            btn = QToolButton()
            btn.setCheckable(True)
            btn.setAutoRaise(True)
            btn.setFixedSize(QSize(28, 28))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(acc.label)
            btn.setAccessibleName("%s accent" % acc.label)
            btn.setStyleSheet(_swatch_style(acc.dark if night else acc.light))
            btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            btn.clicked.connect(self._safe(lambda _c=False, a=aid: self._set("accent", a)))
            self._accent_group.addButton(btn)
            self._swatches[aid] = btn
            accent_row.addWidget(btn)
        accent_row.addStretch(1)
        root.addLayout(accent_row)

        dens_row = QHBoxLayout()
        dens_row.setSpacing(16)
        dens_row.addWidget(self._row_label("Density"))
        for did in DENSITIES:
            rb = QRadioButton(_DENSITY_LABELS.get(did, did.title()))
            rb.toggled.connect(
                self._safe(lambda checked, d=did: checked and self._set("density", d))
            )
            self._density[did] = rb
            dens_row.addWidget(rb)
        dens_row.addStretch(1)
        root.addLayout(dens_row)
        motion_row = QHBoxLayout()
        motion_row.setSpacing(12)
        motion_row.addWidget(self._row_label("Motion"))
        self._motion = {"smooth": QRadioButton("Smooth"), "reduced": QRadioButton("Reduced")}
        self._motion["smooth"].setToolTip("Gentle fades between screens and on hover. Your system's reduced-motion setting still turns them off.")
        motion_group = QButtonGroup(self)
        for value, rb in self._motion.items():
            motion_group.addButton(rb)
            rb.toggled.connect(self._safe(lambda on, v=value: on and self._set("motion", v)))
            motion_row.addWidget(rb)
        motion_row.addStretch(1)
        root.addLayout(motion_row)
        root.addWidget(self._rule())

        # Screens
        root.addWidget(self._section("Screens"))
        self._enabled = QCheckBox("Enable Refine")
        self._enabled.toggled.connect(self._safe(lambda v: self._set("enabled", bool(v))))
        root.addWidget(self._enabled)
        surface_box = QVBoxLayout()
        surface_box.setSpacing(8)
        surface_box.setContentsMargins(26, 0, 0, 0)
        for sid in SURFACE_IDS:
            label, desc = _SURFACES.get(sid, (sid, ""))
            cb = QCheckBox(label)
            cb.toggled.connect(self._safe(lambda v, s=sid: self._set("surfaces." + s, bool(v))))
            d = _muted(QLabel(desc))
            d.setContentsMargins(26, 0, 0, 0)
            cell = QVBoxLayout()
            cell.setSpacing(1)
            cell.addWidget(cb)
            cell.addWidget(d)
            surface_box.addLayout(cell)
            self._surface[sid] = cb
        root.addLayout(surface_box)
        root.addWidget(self._rule())

        # Home screen
        root.addWidget(self._section("Home screen"))
        for hid, hlabel in _HOME:
            cb = QCheckBox(hlabel)
            cb.toggled.connect(self._safe(lambda v, h=hid: self._set("home." + h, bool(v))))
            root.addWidget(cb)
            self._home[hid] = cb
        goal_row = QHBoxLayout()
        goal_row.setContentsMargins(24, 0, 0, 0)
        goal_row.setSpacing(8)
        goal_label = QLabel("Daily goal")
        self._goal = QSpinBox()
        self._goal.setRange(0, MAX_DAILY_GOAL)
        self._goal.setSingleStep(10)
        self._goal.setSpecialValueText("Off")
        self._goal.setSuffix(" cards")
        self._goal.setAccessibleName("Daily goal in cards, 0 for off")
        self._goal.setToolTip("Shown as progress in the Today panel. 0 turns the goal off.")
        self._goal.valueChanged.connect(self._safe(lambda v: self._set("daily_goal", int(v))))
        goal_label.setBuddy(self._goal)
        goal_row.addWidget(goal_label)
        goal_row.addWidget(self._goal)
        goal_row.addStretch(1)
        root.addLayout(goal_row)
        click_row = QHBoxLayout()
        click_row.setContentsMargins(24, 0, 0, 0)
        click_row.setSpacing(12)
        click_row.addWidget(QLabel("Clicking a deck"))
        self._click = {
            "select": QRadioButton("Selects it"),
            "overview": QRadioButton("Opens its overview"),
        }
        self._click["select"].setToolTip("Stay on Home; the headline's Study button follows the selected deck. Double-click opens the overview.")
        self._click["overview"].setToolTip("Anki's usual behaviour.")
        click_group = QButtonGroup(self)
        for value, rb in self._click.items():
            click_group.addButton(rb)
            rb.toggled.connect(self._safe(lambda on, v=value: on and self._set("deck_click", v)))
            click_row.addWidget(rb)
        click_row.addStretch(1)
        root.addLayout(click_row)
        self._ov_chart = QCheckBox("Recent reviews chart on the deck overview")
        self._ov_chart.setToolTip("A small 14-day bar chart for the deck, below the counts on its overview screen.")
        self._ov_chart.toggled.connect(self._safe(lambda v: self._set("overview_chart", bool(v))))
        root.addWidget(self._ov_chart)
        root.addWidget(self._rule())

        # Reviewer
        root.addWidget(self._section("Reviewer"))
        self._ease = QCheckBox("Colour-code answer buttons")
        self._ease.toggled.connect(
            self._safe(lambda v: self._set("reviewer.ease_colors", bool(v)))
        )
        root.addWidget(self._ease)
        self._two = QCheckBox("Show only Again and Good (keys 2 and 4 still work)")
        self._two.toggled.connect(
            self._safe(lambda v: self._set("reviewer.two_buttons", bool(v)))
        )
        root.addWidget(self._two)
        root.addWidget(self._rule())

        # Cards (opt-in: the only settings that affect card content)
        root.addWidget(self._section("Cards (optional)"))
        self._ja = QCheckBox("Japanese reading polish")
        self._ja.setToolTip(
            "Japanese fonts for text your note type marks as Japanese, and tidier furigana.\n"
            "Your card templates still take precedence."
        )
        self._ja.toggled.connect(self._safe(lambda v: self._set("cards.japanese", bool(v))))
        root.addWidget(self._ja)
        self._furi = QCheckBox("Show furigana only on hover or on the answer side")
        self._furi.toggled.connect(self._safe(lambda v: self._set("cards.furigana_hover", bool(v))))
        furi_row = QHBoxLayout()
        furi_row.setContentsMargins(24, 0, 0, 0)
        furi_row.addWidget(self._furi)
        root.addLayout(furi_row)

        root.addStretch(1)
        outer.addWidget(self._rule())

        # Footer
        foot = QHBoxLayout()
        foot.setSpacing(8)
        self._reset_btn = QPushButton("Reset to defaults")
        self._reset_btn.setAutoDefault(False)
        self._reset_btn.clicked.connect(self._safe(self._on_reset))
        self._log_btn = QPushButton("Open log folder")
        self._log_btn.setAutoDefault(False)
        self._log_btn.clicked.connect(self._safe(self._on_open_logs))
        self._close_btn = QPushButton("Close")
        self._close_btn.setDefault(True)
        # Inverted primary: text colour as background, window colour as text.
        self._close_btn.setStyleSheet(
            "QPushButton{background:palette(text);color:palette(window);border:1px solid palette(text);"
            "border-radius:6px;padding:5px 18px;}"
            "QPushButton:focus{border:2px solid palette(highlight);}"
        )
        self._close_btn.clicked.connect(self.close)
        foot.addWidget(self._reset_btn)
        foot.addWidget(self._log_btn)
        foot.addStretch(1)
        foot.addWidget(self._close_btn)
        foot.setContentsMargins(20, 12, 20, 16)
        outer.addLayout(foot)

        chain = (
            list(self._swatches.values())
            + [self._density[d] for d in DENSITIES]
            + [self._motion["smooth"], self._motion["reduced"]]
            + [self._enabled]
            + [self._surface[s] for s in SURFACE_IDS]
            + [self._home[h] for h, _l in _HOME]
            + [self._goal, self._click["select"], self._click["overview"], self._ov_chart]
            + [self._ease, self._two, self._ja, self._furi, self._reset_btn, self._log_btn, self._close_btn]
        )
        for a, b in zip(chain, chain[1:]):
            QDialog.setTabOrder(a, b)

    # -- behaviour -----------------------------------------------------
    def _set(self, path: str, value: Any) -> None:
        self.ctx.config.set(path, value)

    def _on_reset(self) -> None:
        from aqt.utils import askUser

        if askUser("Reset all Refine settings to their defaults?", parent=self):
            self.ctx.config.reset()

    def _on_open_logs(self) -> None:
        from aqt.utils import openFolder

        path = self.ctx.user_files / "logs"
        path.mkdir(parents=True, exist_ok=True)
        openFolder(str(path))

    def sync(self, cfg: dict) -> None:
        """Reflect config on the controls without writing back."""
        self._apply_theme(cfg)
        self._syncing = True
        try:
            acc = cfg.get("accent")
            for aid, btn in self._swatches.items():
                btn.setChecked(aid == acc)
            for did, rb in self._density.items():
                rb.setChecked(did == cfg.get("density"))
            enabled = bool(cfg.get("enabled", True))
            self._enabled.setChecked(enabled)
            surfaces = cfg.get("surfaces", {}) or {}
            for sid, cb in self._surface.items():
                cb.setChecked(bool(surfaces.get(sid, True)))
                cb.setEnabled(enabled)
            home = cfg.get("home") or {}
            for hid, cb in self._home.items():
                cb.setChecked(bool(home.get(hid, True)))
                cb.setEnabled(enabled)
            self._ease.setChecked(bool((cfg.get("reviewer") or {}).get("ease_colors", True)))
            # Default to False to match DEFAULTS (all four buttons visible by default)
            self._two.setChecked(bool((cfg.get("reviewer") or {}).get("two_buttons", False)))
            self._goal.setValue(int(cfg.get("daily_goal", 0) or 0))
            for value, rb in self._motion.items():
                rb.setChecked(cfg.get("motion", "smooth") == value)
            for value, rb in self._click.items():
                rb.setChecked(cfg.get("deck_click", "select") == value)
                rb.setEnabled(enabled)
            self._goal.setEnabled(enabled and bool(home.get("today", True)))
            self._ov_chart.setChecked(bool(cfg.get("overview_chart", True)))
            self._ov_chart.setEnabled(enabled)
            cards = cfg.get("cards") or {}
            self._ja.setChecked(bool(cards.get("japanese", False)))
            self._furi.setChecked(bool(cards.get("furigana_hover", False)))
            self._ja.setEnabled(enabled)
            self._furi.setEnabled(enabled and bool(cards.get("japanese", False)))
        finally:
            self._syncing = False

    def _apply_theme(self, cfg: dict) -> None:
        """Dialog-scoped stylesheet from Refine's tokens, so the dialog matches
        the design and previews accent changes live. Scoped to
        #RefineSettings; Anki's widgets elsewhere are untouched."""
        try:
            from ..theme.tokens import tokens

            t = tokens(_night(), cfg.get("accent", "jade"), cfg.get("density", "comfortable"))
            self.setStyleSheet(
                "QDialog#RefineSettings, QDialog#RefineSettings QScrollArea,"
                " QDialog#RefineSettings QScrollArea > QWidget > QWidget"
                f" {{ background: {t['bg']}; color: {t['text']}; }}"
                f" QDialog#RefineSettings QLabel {{ color: {t['text']}; }}"
                f" QDialog#RefineSettings QLabel#RefineSection {{ color: {t['text-faint']}; }}"
                f" QDialog#RefineSettings QCheckBox, QDialog#RefineSettings QRadioButton {{ color: {t['text']}; spacing: 8px; }}"
                f" QDialog#RefineSettings QCheckBox::indicator:checked, QDialog#RefineSettings QRadioButton::indicator:checked"
                f" {{ background: {t['accent']}; border: 1px solid {t['accent']}; border-radius: 4px; }}"
                f" QDialog#RefineSettings QRadioButton::indicator:checked {{ border-radius: 7px; }}"
                f" QDialog#RefineSettings QCheckBox::indicator, QDialog#RefineSettings QRadioButton::indicator"
                f" {{ width: 14px; height: 14px; }}"
                f" QDialog#RefineSettings QCheckBox::indicator:unchecked, QDialog#RefineSettings QRadioButton::indicator:unchecked"
                f" {{ background: {t['surface']}; border: 1px solid {t['border-strong']}; border-radius: 4px; }}"
                f" QDialog#RefineSettings QRadioButton::indicator:unchecked {{ border-radius: 7px; }}"
                f" QDialog#RefineSettings QPushButton {{ background: {t['surface']}; color: {t['text']};"
                f" border: 1px solid {t['border-strong']}; border-radius: 7px; padding: 6px 14px; }}"
                f" QDialog#RefineSettings QPushButton:hover {{ background: {t['surface-hover']}; }}"
                f" QDialog#RefineSettings QFrame[frameShape=\"4\"] {{ color: {t['border']}; }}"
            )
        except Exception:
            self.ctx.log.exception("settings theming failed")

    def done(self, result: int) -> None:
        global _dialog
        if _dialog is self:
            _dialog = None
        super().done(result)


def _on_config(cfg: dict, changed: frozenset) -> None:
    dlg = _dialog
    if dlg is None:
        return
    try:
        dlg.sync(cfg)
    except Exception:
        dlg.ctx.log.exception("settings sync failed")


def open_settings(ctx: Any) -> None:
    """Show the singleton settings dialog (reuse and raise if already open)."""
    global _dialog
    try:
        if _dialog is not None:
            _dialog.show()
            _dialog.raise_()
            _dialog.activateWindow()
            return
        if not any(c is ctx.config for c in _subscribed_configs):
            ctx.config.subscribe(_on_config)
            _subscribed_configs.append(ctx.config)
        _dialog = _SettingsDialog(ctx)
        _dialog.show()
        _dialog.raise_()
        _dialog.activateWindow()
    except Exception:
        _dialog = None
        ctx.log.exception("could not open settings")

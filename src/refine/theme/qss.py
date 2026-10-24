"""Qt stylesheet generation. QSS has no variables, so values are inlined."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

MARK_BEGIN = "/* refine:begin */"
MARK_END = "/* refine:end */"

_TEMPLATE = """
QMenuBar {
    background: %(bg)s;
}
QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 6px;
}
QMenuBar::item:selected {
    background: %(surface_hover)s;
}
QMenu {
    background: %(surface)s;
    border: 1px solid %(border_strong)s;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 12px 6px 10px;
    margin: 1px 4px;
    border-radius: 6px;
}
QMenu::item:selected {
    background: %(surface_hover)s;
    color: %(text)s;
}
QMenu::item:disabled {
    color: %(text_faint)s;
    background: transparent;
}
QMenu::separator {
    height: 1px;
    background: %(border)s;
    margin: 4px 8px;
}
QToolTip {
    background: %(surface)s;
    color: %(text)s;
    border: 1px solid %(border_strong)s;
    padding: 4px 8px;
    border-radius: 6px;
}
QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: %(border_strong)s;
    border-radius: 4px;
    margin: 2px;
    min-height: 32px;
}
QScrollBar::handle:horizontal {
    background: %(border_strong)s;
    border-radius: 4px;
    margin: 2px;
    min-width: 32px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background: %(text_faint)s;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    background: none;
    border: none;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
    background: none;
    border: none;
}
QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid %(focus)s;
}
"""

# Card browser only, addressed by Anki's own object/class names so other
# dialogs and add-on windows are untouched. Row selection and flag/marked/
# suspended row colours stay Anki's: they carry meaning.
_BROWSER = """
QTableView#tableView {
    background: %(surface)s;
    alternate-background-color: %(bg)s;
    gridline-color: %(border)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
}
QTableView#tableView QHeaderView::section {
    background: %(surface)s;
    color: %(text_muted)s;
    border: none;
    border-bottom: 1px solid %(border)s;
    border-right: 1px solid %(border)s;
    padding: 5px 8px;
    font-weight: 600;
}
SidebarTreeView {
    background: %(bg)s;
    border: none;
}
SidebarTreeView::item {
    padding: 3px 2px;
    border-radius: 6px;
}
SidebarTreeView::item:hover {
    background: %(surface_hover)s;
}
SidebarTreeView::item:selected {
    background: %(surface_active)s;
    color: %(text)s;
}
"""


def render(tok: Dict[str, str]) -> str:
    body = (_TEMPLATE + _BROWSER) % {
        "bg": tok["bg"],
        "surface": tok["surface"],
        "surface_active": tok["surface-active"],
        "text_muted": tok["text-muted"],
        "surface_hover": tok["surface-hover"],
        "border": tok["border"],
        "border_strong": tok["border-strong"],
        "text": tok["text"],
        "text_faint": tok["text-faint"],
        "focus": tok["focus"],
    }
    return "%s%s%s" % (MARK_BEGIN, body, MARK_END)


def _find(s: str) -> Optional[Tuple[int, int]]:
    i = s.find(MARK_BEGIN)
    if i < 0:
        return None
    j = s.find(MARK_END, i)
    if j < 0:
        return None
    return i, j + len(MARK_END)


def strip(stylesheet: str) -> str:
    s = stylesheet
    while True:
        span = _find(s)
        if span is None:
            return s
        a, b = span
        if s[b:b + 1] == "\n":
            b += 1
        s = s[:a] + s[b:]


def splice(stylesheet: str, block: str) -> str:
    block = block.rstrip("\n")
    span = _find(stylesheet)
    if span is not None:
        a, b = span
        return stylesheet[:a] + block + stylesheet[b:]
    if not stylesheet:
        return block + "\n"
    sep = "" if stylesheet.endswith("\n") else "\n"
    return stylesheet + sep + block + "\n"

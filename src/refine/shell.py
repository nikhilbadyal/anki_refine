"""Sidebar + header markup (the design's app shell). Pure functions.

Every action goes through Refine's bridge (pycmd("refine:sidebar:...")) and
runs the same Anki function as the stock toolbar or shortcut, so behaviour is
unchanged; only where the controls live changes.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

# Simple 16px stroke icons (drawn for Refine; no third-party icon set).
_ICONS = {
    "decks": '<path d="M3 5.5 8 3l5 2.5L8 8 3 5.5Z"/><path d="m3 8.5 5 2.5 5-2.5"/><path d="m3 11.5 5 2.5 5-2.5"/>',
    "add": '<path d="M8 3v10M3 8h10"/>',
    "browse": '<circle cx="7" cy="7" r="4"/><path d="m10 10 3 3"/>',
    "stats": '<path d="M3 13V8M8 13V3M13 13V6"/>',
    "options": '<path d="M3 5h6M11 5h2M3 11h2M7 11h6"/><circle cx="10" cy="5" r="1.5"/><circle cx="6" cy="11" r="1.5"/>',
    "sync": '<path d="M13 6.5A5 5 0 0 0 4 5M3 9.5A5 5 0 0 0 12 11"/><path d="M4 2.5V5h2.5M12 13.5V11H9.5"/>',
    "addon": '<rect x="3" y="3" width="4" height="4" rx="1"/><rect x="9" y="3" width="4" height="4" rx="1"/><rect x="3" y="9" width="4" height="4" rx="1"/><rect x="9" y="9" width="4" height="4" rx="1"/>',
}


def icon(name: str) -> str:
    return (
        '<svg class="rf-ico" viewBox="0 0 16 16" width="16" height="16" fill="none" '
        'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true">{_ICONS.get(name, _ICONS["addon"])}</svg>'
    )


@dataclass(frozen=True)
class NavItem:
    id: str
    label: str
    key: str  # shortcut hint shown on the right ("" for none)


NAV = (
    NavItem("decks", "Decks", "D"),
    NavItem("stats", "Stats", "T"),
    NavItem("browse", "Browse", "B"),
    NavItem("add", "Add cards", "A"),
    NavItem("options", "Deck options", ""),
)

STOCK_TOOLBAR_CMDS = {"decks", "add", "browse", "stats", "sync"}
_PYCMD = re.compile(r"pycmd\(\s*['\"]([^'\"]+)['\"]")
_TAGS = re.compile(r"<[^>]+>")


def extra_toolbar_links(links: list[str]) -> list[tuple[str, str]]:
    """(command, label) for toolbar links other add-ons added, so the sidebar
    can offer them while the top toolbar is hidden."""
    out = []
    for link in links:
        m = _PYCMD.search(link)
        if not m or m.group(1) in STOCK_TOOLBAR_CMDS:
            continue
        label = html.unescape(_TAGS.sub("", link)).strip()
        if label:
            out.append((m.group(1), label))
    return out


def _cmd(action: str) -> str:
    return f"return pycmd('refine:sidebar:{action}')"


def sidebar_html(active: str, profile: str, extras: list[tuple[str, str]]) -> str:
    items = []
    for n in NAV:
        cur = ' aria-current="page"' if n.id == active else ""
        key = f'<kbd class="rf-key">{n.key}</kbd>' if n.key else ""
        items.append(
            f'<button class="rf-nav-item" type="button"{cur} onclick="{_cmd("go:" + n.id)}" '
            f'title="{html.escape(n.label)}">{icon(n.id)}<span class="rf-nav-label">{html.escape(n.label)}</span>{key}</button>'
        )
    extra = ""
    if extras:
        rows = "".join(
            f'<button class="rf-nav-item rf-nav-addon" type="button" '
            f'onclick="{_cmd("toolbar:" + html.escape(cmd, quote=True))}" title="{html.escape(label)}">'
            f'{icon("addon")}<span class="rf-nav-label">{html.escape(label)}</span></button>'
            for cmd, label in extras
        )
        extra = f'<div class="rf-nav-group"><div class="rf-nav-heading">Add-ons</div>{rows}</div>'
    initial = html.escape((profile or "A")[:1].upper())
    return (
        '<nav class="rf-shell" aria-label="Main">'
        f'<div class="rf-brand"><div class="rf-brand-mark" aria-hidden="true">A</div>'
        f'<div class="rf-brand-text"><span class="rf-brand-name">Anki</span>'
        f'<span class="rf-brand-profile" title="Profile">{html.escape(profile or "")}</span></div>'
        f'<span class="rf-brand-initial" aria-hidden="true">{initial}</span></div>'
        f'<div class="rf-nav">{"".join(items)}</div>'
        f"{extra}"
        '<div class="rf-shell-foot">'
        f'<button class="rf-nav-item rf-sync" type="button" onclick="{_cmd("go:sync")}" title="Sync (Y)">'
        f'{icon("sync")}<span class="rf-nav-label">Sync</span>'
        '<kbd class="rf-key">Y</kbd></button>'
        "</div></nav>"
    )


def header_html(title: str, subtitle: str = "") -> str:
    sub = f'<span class="rf-header-sub">{html.escape(subtitle)}</span>' if subtitle else ""
    return (
        '<header class="rf-header">'
        f'<div class="rf-header-title"><h1>{html.escape(title)}</h1>{sub}</div>'
        '<div class="rf-header-actions">'
        '<label class="rf-search"><span class="rf-visually-hidden">Search cards</span>'
        f'{icon("browse")}<input type="search" placeholder="Search cards…" '
        "onkeydown=\"if(event.key==='Enter'){pycmd('refine:sidebar:search:'+this.value);this.value='';return false;}\">"
        '<kbd class="rf-key">Ctrl K</kbd></label>'
        f'<button class="rf-btn rf-btn-primary" type="button" onclick="{_cmd("go:add")}">Add card</button>'
        "</div></header>"
    )

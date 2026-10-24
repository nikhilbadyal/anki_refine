"""Stdlib-only helpers for inspecting captured Anki HTML snapshots.

Used by scripts/devenv.py (cross-version class/id inventory) and by
tests/contract (selector contract). Supports a deliberately small selector
syntax: `tag`, `.class`, `#id`, `[attr]`, `[attr=value]`, combined without
spaces (e.g. `tr.deck.current`, `button[data-ease=3]`). No descendant
combinators: the contract is about which hooks into the DOM exist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path


@dataclass
class Element:
    tag: str
    attrs: dict[str, str]

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())


@dataclass
class Inventory:
    elements: list[Element] = field(default_factory=list)

    def classes(self) -> set[str]:
        out: set[str] = set()
        for e in self.elements:
            out |= e.classes
        return out

    def ids(self) -> set[str]:
        # numeric ids are deck ids; they differ per collection, not per version
        return {
            e.attrs["id"]
            for e in self.elements
            if e.attrs.get("id") and not e.attrs["id"].isdigit()
        }

    def data_attrs(self) -> set[str]:
        return {k for e in self.elements for k in e.attrs if k.startswith("data-")}

    def matches(self, selector: str) -> int:
        sel = parse_selector(selector)
        return sum(1 for e in self.elements if sel.match(e))


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.inv = Inventory()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.inv.elements.append(Element(tag, {k: v or "" for k, v in attrs}))

    handle_startendtag = handle_starttag


def inventory(html: str) -> Inventory:
    c = _Collector()
    c.feed(html)
    return c.inv


def inventory_file(path: Path) -> Inventory:
    return inventory(path.read_text(encoding="utf-8"))


_TOKEN = re.compile(r"([.#]?)([A-Za-z_][\w-]*)|\[([\w-]+)(?:=([^\]]+))?\]")


@dataclass
class Selector:
    tag: str | None
    classes: set[str]
    id: str | None
    attrs: list[tuple[str, str | None]]

    def match(self, e: Element) -> bool:
        if self.tag and e.tag != self.tag:
            return False
        if self.id and e.attrs.get("id") != self.id:
            return False
        if not self.classes <= e.classes:
            return False
        for name, value in self.attrs:
            if name not in e.attrs:
                return False
            if value is not None and e.attrs[name] != value.strip("'\""):
                return False
        return True


def parse_selector(text: str) -> Selector:
    tag: str | None = None
    classes: set[str] = set()
    ident: str | None = None
    attrs: list[tuple[str, str | None]] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise ValueError(f"unsupported selector syntax: {text!r}")
        prefix, name, attr, value = m.groups()
        if attr:
            attrs.append((attr, value))
        elif prefix == ".":
            classes.add(name)
        elif prefix == "#":
            ident = name
        else:
            tag = name
        pos = m.end()
    return Selector(tag, classes, ident, attrs)

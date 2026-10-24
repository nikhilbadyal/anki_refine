"""Shared runtime context handed to surfaces and UI."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ConfigStore
from .guard import Guard


@dataclass
class Context:
    mw: Any
    config: ConfigStore
    guard: Guard
    log: logging.Logger
    addon_package: str
    addon_dir: Path

    @property
    def web_base(self) -> str:
        return f"/_addons/{self.addon_package}/web"

    @property
    def user_files(self) -> Path:
        return self.addon_dir / "user_files"

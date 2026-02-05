"""Command palette - Quick fuzzy search with Ctrl+K."""

import tkinter as tk
from dataclasses import dataclass
from typing import Callable

from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PaletteResult:
    label: str
    category: str
    action: Callable


def show_palette(parent: tk.Widget) -> None:
    """Show command palette."""
    raise NotImplementedError("Phase 6, Step 6.5")


def search(query: str) -> list[PaletteResult]:
    """Search all searchable items."""
    raise NotImplementedError("Phase 6, Step 6.5")


def execute(result: PaletteResult) -> None:
    """Execute selected command."""
    raise NotImplementedError("Phase 6, Step 6.5")

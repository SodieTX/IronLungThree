"""Keyboard shortcuts configuration."""

import tkinter as tk
from typing import Callable, Dict
from src.core.logging import get_logger

logger = get_logger(__name__)

# Shortcut definitions
SHORTCUTS: Dict[str, str] = {
    "<Return>": "confirm",
    "<Escape>": "cancel",
    "<Control-z>": "undo",
    "<Tab>": "skip",
    "<Control-d>": "defer",
    "<Control-f>": "quick_lookup",
    "<Control-m>": "demo_invite",
    "<Control-e>": "send_email",
    "<Control-k>": "command_palette",
    "<Control-Shift-f>": "focus_mode",
}


def bind_shortcuts(root: tk.Tk, handlers: Dict[str, Callable]) -> None:
    """Bind keyboard shortcuts to handlers."""
    raise NotImplementedError("Phase 2, Step 2.13")


def unbind_shortcuts(root: tk.Tk) -> None:
    """Unbind all shortcuts."""
    raise NotImplementedError("Phase 2, Step 2.13")

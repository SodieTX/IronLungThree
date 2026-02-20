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
    """Bind keyboard shortcuts to handlers.

    Args:
        root: The Tk root window.
        handlers: Mapping of action names to callables.
            Action names must match values in SHORTCUTS dict.
    """
    bound = 0
    for key_seq, action_name in SHORTCUTS.items():
        handler = handlers.get(action_name)
        if handler is None:
            continue

        def _make_callback(h: Callable) -> Callable[["tk.Event[tk.Misc]"], None]:
            def callback(event: "tk.Event[tk.Misc]") -> None:
                h()

            return callback

        try:
            root.bind(key_seq, _make_callback(handler))
            bound += 1
            logger.debug(f"Bound {key_seq} -> {action_name}")
        except tk.TclError as exc:
            logger.warning(f"Failed to bind {key_seq}: {exc}")

    logger.info(f"Bound {bound} keyboard shortcuts")


def unbind_shortcuts(root: tk.Tk) -> None:
    """Unbind all registered shortcuts."""
    for key_seq in SHORTCUTS:
        try:
            root.unbind(key_seq)
        except tk.TclError:
            pass
    logger.info("All keyboard shortcuts unbound")

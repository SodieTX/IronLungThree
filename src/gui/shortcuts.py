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

# Keep track of bound sequences for unbinding
_bound_sequences: list[str] = []


def bind_shortcuts(root: tk.Tk, handlers: Dict[str, Callable]) -> None:
    """Bind keyboard shortcuts to handlers.

    Only binds shortcuts whose action name appears in *handlers*.
    Unknown actions are silently skipped.

    Args:
        root: The root Tk window
        handlers: Map of action name -> callable (e.g. {"confirm": on_confirm})
    """
    global _bound_sequences
    _bound_sequences = []

    for sequence, action in SHORTCUTS.items():
        handler = handlers.get(action)
        if handler is None:
            continue

        # Wrap to swallow the event argument tkinter passes
        def _make_handler(fn: Callable) -> Callable:
            def wrapper(event: tk.Event = None) -> str:  # type: ignore[assignment]
                fn()
                return "break"  # prevent further propagation

            return wrapper

        root.bind(sequence, _make_handler(handler))
        _bound_sequences.append(sequence)
        logger.debug(
            "Shortcut bound",
            extra={"context": {"sequence": sequence, "action": action}},
        )

    logger.info(
        "Keyboard shortcuts bound",
        extra={"context": {"count": len(_bound_sequences)}},
    )


def unbind_shortcuts(root: tk.Tk) -> None:
    """Unbind all previously-bound shortcuts."""
    global _bound_sequences
    for sequence in _bound_sequences:
        try:
            root.unbind(sequence)
        except tk.TclError:
            pass
    count = len(_bound_sequences)
    _bound_sequences = []
    logger.debug("Shortcuts unbound", extra={"context": {"count": count}})

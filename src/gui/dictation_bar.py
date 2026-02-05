"""Dictation bar - Persistent input at bottom of every tab."""

import tkinter as tk
from typing import Callable, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


class DictationBar(tk.Frame):
    """Persistent text input widget."""

    def __init__(
        self,
        parent: tk.Widget,
        on_submit: Callable[[str], None],
        placeholder: str = "Speak or type...",
    ):
        super().__init__(parent)
        self._on_submit = on_submit
        self._placeholder = placeholder
        raise NotImplementedError("Phase 4, Step 4.1")

    def get_input(self) -> str:
        """Get current input text."""
        raise NotImplementedError("Phase 4, Step 4.1")

    def clear(self) -> None:
        """Clear input."""
        raise NotImplementedError("Phase 4, Step 4.1")

    def show_response(self, text: str) -> None:
        """Show Anne's response above input."""
        raise NotImplementedError("Phase 4, Step 4.1")

    def set_manual_mode(self, enabled: bool) -> None:
        """Enable manual mode (for offline)."""
        raise NotImplementedError("Phase 4, Step 4.10")

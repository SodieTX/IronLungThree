"""Email recall dialog - The "Oh Shit" button."""

import tkinter as tk

from src.core.logging import get_logger

logger = get_logger(__name__)


class EmailRecallDialog:
    """Email recall attempt dialog."""

    def __init__(self, parent: tk.Widget, message_id: str):
        self.parent = parent
        self.message_id = message_id
        raise NotImplementedError("Phase 3, Step 3.11")

    def show(self) -> None:
        """Display dialog."""
        raise NotImplementedError("Phase 3, Step 3.11")

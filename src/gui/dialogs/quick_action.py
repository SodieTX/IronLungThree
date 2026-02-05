"""Quick action dialog for fast status changes."""

import tkinter as tk

from src.core.logging import get_logger

logger = get_logger(__name__)


class QuickActionDialog:
    """Quick action dialog."""

    def __init__(self, parent: tk.Widget, prospect_id: int):
        self.parent = parent
        self.prospect_id = prospect_id
        raise NotImplementedError("Phase 2")

    def show(self) -> bool:
        """Display dialog. Returns True if action taken."""
        raise NotImplementedError("Phase 2")

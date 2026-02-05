"""Prospect card display widget."""

import tkinter as tk
from typing import Optional
from src.db.models import Prospect, Company
from src.core.logging import get_logger

logger = get_logger(__name__)


class ProspectCard(tk.Frame):
    """Prospect card widget with glance, call, and deep dive views."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)
        self._prospect: Optional[Prospect] = None
        self._company: Optional[Company] = None
        self._view_mode = "glance"  # glance, call, deep
        raise NotImplementedError("Phase 2, Step 2.5")

    def set_prospect(
        self,
        prospect: Prospect,
        company: Company,
        activities: list,
        intel: list,
    ) -> None:
        """Set prospect to display."""
        raise NotImplementedError("Phase 2, Step 2.5")

    def set_view_mode(self, mode: str) -> None:
        """Set view mode: glance, call, or deep."""
        raise NotImplementedError("Phase 2, Step 2.5")

    def enter_call_mode(self) -> None:
        """Enter call mode view."""
        raise NotImplementedError("Phase 3, Step 3.9")

    def exit_call_mode(self) -> None:
        """Exit call mode, return to glance."""
        raise NotImplementedError("Phase 3, Step 3.9")

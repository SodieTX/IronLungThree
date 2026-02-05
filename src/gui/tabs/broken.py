"""Broken tab - Records missing phone/email."""

from src.gui.tabs import TabBase
from src.core.logging import get_logger

logger = get_logger(__name__)


class BrokenTab(TabBase):
    """Broken prospects management."""

    def refresh(self) -> None:
        raise NotImplementedError("Phase 2, Step 2.10")

    def on_activate(self) -> None:
        raise NotImplementedError("Phase 2, Step 2.10")

    def show_needs_confirmation(self) -> None:
        """Show records with research findings to confirm."""
        raise NotImplementedError("Phase 2, Step 2.10")

    def show_in_progress(self) -> None:
        """Show records currently being researched."""
        raise NotImplementedError("Phase 2, Step 2.10")

    def show_manual_needed(self) -> None:
        """Show records needing manual research."""
        raise NotImplementedError("Phase 2, Step 2.10")

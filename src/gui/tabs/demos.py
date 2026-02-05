"""Demos tab - Demo invite creation and tracking."""

from src.core.logging import get_logger
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class DemosTab(TabBase):
    """Demo management."""

    def refresh(self) -> None:
        raise NotImplementedError("Phase 3, Step 3.5")

    def on_activate(self) -> None:
        raise NotImplementedError("Phase 3, Step 3.5")

    def create_invite(self) -> None:
        """Open demo invite creator."""
        raise NotImplementedError("Phase 3, Step 3.5")

    def show_upcoming(self) -> None:
        """Show upcoming demos."""
        raise NotImplementedError("Phase 3, Step 3.5")

    def show_completed(self) -> None:
        """Show completed demos."""
        raise NotImplementedError("Phase 3, Step 3.5")

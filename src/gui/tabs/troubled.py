"""Troubled tab - Problem cards needing attention."""

from src.core.logging import get_logger
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class TroubledTab(TabBase):
    """Problem cards management."""

    def refresh(self) -> None:
        raise NotImplementedError("Phase 6, Step 6.9")

    def on_activate(self) -> None:
        raise NotImplementedError("Phase 6, Step 6.9")

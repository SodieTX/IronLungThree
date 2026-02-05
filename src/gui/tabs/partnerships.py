"""Partnerships tab - Non-prospect relationship contacts."""

from src.gui.tabs import TabBase
from src.core.logging import get_logger

logger = get_logger(__name__)


class PartnershipsTab(TabBase):
    """Partnership contacts management."""

    def refresh(self) -> None:
        raise NotImplementedError("Phase 7, Step 7.9")

    def on_activate(self) -> None:
        raise NotImplementedError("Phase 7, Step 7.9")

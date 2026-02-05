"""Today tab - Morning brief and card processing."""

from src.core.logging import get_logger
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class TodayTab(TabBase):
    """Today tab with queue processing."""

    def refresh(self) -> None:
        raise NotImplementedError("Phase 2, Step 2.6")

    def on_activate(self) -> None:
        raise NotImplementedError("Phase 2, Step 2.6")

    def show_morning_brief(self) -> None:
        """Display morning brief dialog."""
        raise NotImplementedError("Phase 2, Step 2.8")

    def start_processing(self) -> None:
        """Start card processing loop."""
        raise NotImplementedError("Phase 2, Step 2.6")

    def next_card(self) -> None:
        """Move to next card in queue."""
        raise NotImplementedError("Phase 2, Step 2.6")

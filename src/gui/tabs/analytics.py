"""Analytics tab - Performance metrics and reporting."""

from src.gui.tabs import TabBase
from src.core.logging import get_logger

logger = get_logger(__name__)


class AnalyticsTab(TabBase):
    """Performance analytics."""

    def refresh(self) -> None:
        raise NotImplementedError("Phase 7, Step 7.8")

    def on_activate(self) -> None:
        raise NotImplementedError("Phase 7, Step 7.8")

    def generate_report(self, month: str) -> None:
        """Generate monthly report."""
        raise NotImplementedError("Phase 7, Step 7.8")

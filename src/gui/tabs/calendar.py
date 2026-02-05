"""Calendar tab - Day/week views and follow-ups."""

from src.gui.tabs import TabBase
from src.core.logging import get_logger

logger = get_logger(__name__)


class CalendarTab(TabBase):
    """Calendar view with follow-ups and demos."""

    def refresh(self) -> None:
        raise NotImplementedError("Phase 2, Step 2.9")

    def on_activate(self) -> None:
        raise NotImplementedError("Phase 2, Step 2.9")

    def show_day_view(self) -> None:
        """Show hour-by-hour day view."""
        raise NotImplementedError("Phase 2, Step 2.9")

    def show_week_view(self) -> None:
        """Show seven-column week view."""
        raise NotImplementedError("Phase 2, Step 2.9")

    def show_monthly_buckets(self) -> None:
        """Show parked contacts by month."""
        raise NotImplementedError("Phase 2, Step 2.9")

"""Troubled tab - Problem cards needing attention.

Displays overdue, stalled, and suspect-data prospects.
Data provided by TroubledCardsService.
"""

from src.core.logging import get_logger
from src.engine.troubled_cards import TroubledCardsService
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class TroubledTab(TabBase):
    """Problem cards management.

    Shows three categories:
    - Overdue: follow-ups past due by 2+ days
    - Stalled: engaged with no activity in 14+ days
    - Suspect data: flagged contact methods
    """

    def refresh(self) -> None:
        """Reload troubled cards from database."""
        svc = TroubledCardsService(self.db)
        self._cards = svc.get_troubled_cards()
        logger.debug(
            "Troubled tab refreshed",
            extra={"context": {"count": len(self._cards)}},
        )

    def on_activate(self) -> None:
        """Called when tab becomes visible."""
        self.refresh()

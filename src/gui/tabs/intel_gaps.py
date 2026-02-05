"""Intel gaps tab - Missing information audit.

Displays prospects with missing non-critical data.
Data provided by IntelGapsService.
"""

from src.core.logging import get_logger
from src.engine.intel_gaps import IntelGapsService
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class IntelGapsTab(TabBase):
    """Missing intel audit.

    Shows prospects missing:
    - Company domain/website
    - Job title
    - Company size
    - Intel nuggets (engaged only)
    """

    def refresh(self) -> None:
        """Reload intel gaps from database."""
        svc = IntelGapsService(self.db)
        self._gaps = svc.get_intel_gaps()
        self._summary = svc.get_gap_summary()
        logger.debug(
            "Intel gaps tab refreshed",
            extra={"context": {"total_gaps": len(self._gaps), "summary": self._summary}},
        )

    def on_activate(self) -> None:
        """Called when tab becomes visible."""
        self.refresh()

"""Pipeline tab - Full database view with filtering."""

from src.core.logging import get_logger
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class PipelineTab(TabBase):
    """Full pipeline view with filtering and bulk operations."""

    def refresh(self) -> None:
        raise NotImplementedError("Phase 1, Step 1.14")

    def on_activate(self) -> None:
        raise NotImplementedError("Phase 1, Step 1.14")

    def apply_filters(self) -> None:
        """Apply current filter settings."""
        raise NotImplementedError("Phase 1, Step 1.14")

    def export_view(self) -> None:
        """Export current view to CSV."""
        raise NotImplementedError("Phase 1, Step 1.14")

    def bulk_move(self, population: str) -> None:
        """Bulk move selected to population."""
        raise NotImplementedError("Phase 1, Step 1.14")

    def bulk_park(self, month: str) -> None:
        """Bulk park selected to month."""
        raise NotImplementedError("Phase 1, Step 1.14")

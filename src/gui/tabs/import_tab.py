"""Import tab - File upload, mapping, and preview."""

from src.gui.tabs import TabBase
from src.core.logging import get_logger

logger = get_logger(__name__)


class ImportTab(TabBase):
    """Import functionality."""

    def refresh(self) -> None:
        raise NotImplementedError("Phase 1, Step 1.15")

    def on_activate(self) -> None:
        raise NotImplementedError("Phase 1, Step 1.15")

    def select_file(self) -> None:
        """Open file dialog."""
        raise NotImplementedError("Phase 1, Step 1.15")

    def show_mapping(self) -> None:
        """Show column mapping interface."""
        raise NotImplementedError("Phase 1, Step 1.15")

    def preview_import(self) -> None:
        """Show import preview dialog."""
        raise NotImplementedError("Phase 1, Step 1.15")

    def execute_import(self) -> None:
        """Execute the import."""
        raise NotImplementedError("Phase 1, Step 1.15")

"""Settings tab - Configuration, backup, recovery."""

from src.core.logging import get_logger
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class SettingsTab(TabBase):
    """Application settings."""

    def refresh(self) -> None:
        raise NotImplementedError("Phase 1, Step 1.16")

    def on_activate(self) -> None:
        raise NotImplementedError("Phase 1, Step 1.16")

    def create_backup(self) -> None:
        """Trigger manual backup."""
        raise NotImplementedError("Phase 1, Step 1.16")

    def restore_backup(self) -> None:
        """Open restore dialog."""
        raise NotImplementedError("Phase 1, Step 1.16")

    def save_settings(self) -> None:
        """Save settings changes."""
        raise NotImplementedError("Phase 1, Step 1.16")

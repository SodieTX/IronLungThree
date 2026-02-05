"""Settings tab - Configuration, backup, recovery, service status.

Includes a service readiness panel that shows which external
integrations are configured and which credentials are missing.
This is the first place the user looks when something isn't working.
"""

from src.core.logging import get_logger
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class SettingsTab(TabBase):
    """Application settings.

    When implemented, the refresh() method will include a call to
    get_service_status_text() from src.gui.service_guard to display
    the current service readiness in the settings panel.
    """

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

    def get_service_readiness(self) -> str:
        """Get formatted service readiness for display.

        Returns:
            Multi-line status string
        """
        from src.gui.service_guard import get_service_status_text

        return get_service_status_text()

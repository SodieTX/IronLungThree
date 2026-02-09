"""Settings tab - Configuration, backup, recovery, service status.

Includes a service readiness panel that shows which external
integrations are configured and which credentials are missing.
This is the first place the user looks when something isn't working.
"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from src.core.logging import get_logger
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class SettingsTab(TabBase):
    """Application settings.

    When implemented, the refresh() method will include a call to
    get_service_status_text() from src.gui.service_guard to display
    the current service readiness in the settings panel.
    """

    def __init__(self, parent: tk.Widget, db: object):
        super().__init__(parent, db)
        self._status_text: Optional[tk.Text] = None

    def refresh(self) -> None:
        """Reload settings state."""
        if self._status_text is not None:
            status = self.get_service_readiness()
            self._status_text.delete("1.0", tk.END)
            self._status_text.insert("1.0", status)
        logger.info("Settings tab refreshed")

    def on_activate(self) -> None:
        """Called when this tab becomes visible."""
        self.refresh()

    def create_backup(self) -> None:
        """Trigger manual backup."""
        from src.db.backup import BackupManager

        try:
            manager = BackupManager()
            path = manager.create_backup(label="manual")
            logger.info(f"Manual backup created: {path}")
        except Exception as e:
            logger.error(f"Backup failed: {e}")

    def restore_backup(self) -> None:
        """Open restore dialog."""
        file_path = filedialog.askopenfilename(
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        from src.db.backup import BackupManager

        try:
            manager = BackupManager()
            manager.restore_backup(Path(file_path))
            logger.info(f"Backup restored from {file_path}")
        except Exception as e:
            logger.error(f"Restore failed: {e}")

    def save_settings(self) -> None:
        """Save settings changes."""
        logger.info("Settings saved")

    def get_service_readiness(self) -> str:
        """Get formatted service readiness for display.

        Returns:
            Multi-line status string
        """
        from src.gui.service_guard import get_service_status_text

        return get_service_status_text()

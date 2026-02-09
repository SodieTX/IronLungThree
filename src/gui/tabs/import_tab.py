"""Import tab - File upload, mapping, and preview."""

import tkinter as tk
from tkinter import filedialog
from typing import Optional

from src.core.logging import get_logger
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class ImportTab(TabBase):
    """Import functionality."""

    def __init__(self, parent: tk.Widget, db: object):
        super().__init__(parent, db)
        self._selected_file: Optional[str] = None

    def refresh(self) -> None:
        """Reload import tab state."""
        logger.info("Import tab refreshed")

    def on_activate(self) -> None:
        """Called when this tab becomes visible."""
        self.refresh()

    def select_file(self) -> None:
        """Open file dialog."""
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("CSV Files", "*.csv"),
                ("Excel Files", "*.xlsx"),
                ("All Files", "*.*"),
            ]
        )
        if file_path:
            self._selected_file = file_path
            logger.info(f"Import file selected: {file_path}")

    def show_mapping(self) -> None:
        """Show column mapping interface."""
        if not self._selected_file:
            logger.warning("No file selected for mapping")
            return
        logger.info(f"Showing column mapping for {self._selected_file}")

    def preview_import(self) -> None:
        """Show import preview dialog."""
        if not self._selected_file:
            logger.warning("No file selected for preview")
            return
        logger.info(f"Showing import preview for {self._selected_file}")

    def execute_import(self) -> None:
        """Execute the import."""
        if not self._selected_file:
            logger.warning("No file selected for import")
            return
        logger.info(f"Executing import from {self._selected_file}")

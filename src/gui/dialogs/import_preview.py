"""Import preview dialog."""

import tkinter as tk
from src.db.intake import ImportPreview
from src.core.logging import get_logger

logger = get_logger(__name__)


class ImportPreviewDialog:
    """Import preview and confirmation dialog."""

    def __init__(self, parent: tk.Widget, preview: ImportPreview):
        self.parent = parent
        self.preview = preview
        raise NotImplementedError("Phase 1, Step 1.15")

    def show(self) -> bool:
        """Display dialog. Returns True if confirmed."""
        raise NotImplementedError("Phase 1, Step 1.15")

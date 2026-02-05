"""Edit prospect dialog."""

import tkinter as tk

from src.core.logging import get_logger
from src.db.models import Prospect

logger = get_logger(__name__)


class EditProspectDialog:
    """Prospect editing form dialog."""

    def __init__(self, parent: tk.Widget, prospect: Prospect):
        self.parent = parent
        self.prospect = prospect
        raise NotImplementedError("Phase 2")

    def show(self) -> bool:
        """Display dialog. Returns True if saved."""
        raise NotImplementedError("Phase 2")

    def get_updated_prospect(self) -> Prospect:
        """Get updated prospect data."""
        raise NotImplementedError("Phase 2")

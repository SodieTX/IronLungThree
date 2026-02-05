"""Closed won dialog for deal capture."""

import tkinter as tk
from typing import Optional
from decimal import Decimal
from src.core.logging import get_logger

logger = get_logger(__name__)


class ClosedWonDialog:
    """Deal capture dialog."""

    def __init__(self, parent: tk.Widget, prospect_id: int):
        self.parent = parent
        self.prospect_id = prospect_id
        self.deal_value: Optional[Decimal] = None
        raise NotImplementedError("Phase 3, Step 3.10")

    def show(self) -> bool:
        """Display dialog. Returns True if captured."""
        raise NotImplementedError("Phase 3, Step 3.10")

"""Tab interface contract and implementations.

All tabs inherit from TabBase and implement:
    - refresh(): Reload data
    - on_activate(): Called when tab becomes visible
    - on_deactivate(): Called when leaving tab
"""

import tkinter as tk
from abc import ABC, abstractmethod
from typing import Optional


class TabBase(ABC):
    """Abstract base class for all tabs."""

    def __init__(self, parent: tk.Widget, db):
        self.parent = parent
        self.db = db
        self.frame: Optional[tk.Frame] = None

    @abstractmethod
    def refresh(self) -> None:
        """Reload tab data from database."""
        pass

    @abstractmethod
    def on_activate(self) -> None:
        """Called when this tab becomes visible."""
        pass

    def on_deactivate(self) -> None:
        """Called when leaving this tab."""
        pass


__all__ = ["TabBase"]

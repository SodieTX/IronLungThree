"""Morning brief dialog."""

import tkinter as tk
from typing import Callable
from src.core.logging import get_logger

logger = get_logger(__name__)


class MorningBriefDialog:
    """Morning brief display dialog."""

    def __init__(self, parent: tk.Widget, brief_content: str, on_ready: Callable):
        self.parent = parent
        self.brief_content = brief_content
        self.on_ready = on_ready
        raise NotImplementedError("Phase 2, Step 2.8")

    def show(self) -> None:
        """Display the dialog."""
        raise NotImplementedError("Phase 2, Step 2.8")

    def close(self) -> None:
        """Close dialog and start processing."""
        raise NotImplementedError("Phase 2, Step 2.8")

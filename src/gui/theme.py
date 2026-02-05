"""Visual theme and styling."""

import tkinter as tk
from tkinter import ttk
from src.core.logging import get_logger

logger = get_logger(__name__)


# Color palette
COLORS = {
    "bg": "#f5f5f5",
    "bg_alt": "#ffffff",
    "fg": "#333333",
    "accent": "#0066cc",
    "success": "#28a745",
    "warning": "#ffc107",
    "danger": "#dc3545",
    "muted": "#6c757d",
}

# Fonts
FONTS = {
    "default": ("Segoe UI", 10),
    "large": ("Segoe UI", 12),
    "small": ("Segoe UI", 9),
    "mono": ("Consolas", 10),
}


def apply_theme(root: tk.Tk) -> None:
    """Apply theme to application."""
    raise NotImplementedError("Phase 1, Step 1.14")


def configure_styles() -> None:
    """Configure ttk styles."""
    raise NotImplementedError("Phase 1, Step 1.14")

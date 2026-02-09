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
    root.configure(bg=COLORS["bg"])
    configure_styles()
    logger.info("Theme applied")


def configure_styles() -> None:
    """Configure ttk styles."""
    style = ttk.Style()
    style.theme_use("clam")

    style.configure("TFrame", background=COLORS["bg"])
    style.configure(
        "TLabel",
        background=COLORS["bg"],
        foreground=COLORS["fg"],
        font=FONTS["default"],
    )
    style.configure(
        "TButton",
        font=FONTS["default"],
        padding=6,
    )
    style.configure(
        "TNotebook",
        background=COLORS["bg"],
    )
    style.configure(
        "TNotebook.Tab",
        font=FONTS["default"],
        padding=(12, 4),
    )
    style.configure(
        "Treeview",
        font=FONTS["default"],
        rowheight=28,
    )
    style.configure(
        "Treeview.Heading",
        font=FONTS["default"],
    )
    logger.info("TTK styles configured")

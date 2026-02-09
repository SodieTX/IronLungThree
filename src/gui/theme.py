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
    """Apply theme colours and fonts to the root window."""
    root.configure(bg=COLORS["bg"])
    root.option_add("*Font", FONTS["default"])
    root.option_add("*Background", COLORS["bg"])
    root.option_add("*Foreground", COLORS["fg"])
    configure_styles()
    logger.debug("Theme applied")


def configure_styles() -> None:
    """Configure ttk widget styles."""
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass  # fallback to default theme

    # General
    style.configure(".", font=FONTS["default"], background=COLORS["bg"], foreground=COLORS["fg"])

    # Frame
    style.configure("TFrame", background=COLORS["bg"])
    style.configure("Card.TFrame", background=COLORS["bg_alt"], relief="solid", borderwidth=1)

    # Labels
    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["fg"])
    style.configure("Heading.TLabel", font=("Segoe UI", 14, "bold"))
    style.configure("SubHeading.TLabel", font=("Segoe UI", 12, "bold"))
    style.configure("Muted.TLabel", foreground=COLORS["muted"])
    style.configure("Success.TLabel", foreground=COLORS["success"])
    style.configure("Danger.TLabel", foreground=COLORS["danger"])
    style.configure("Accent.TLabel", foreground=COLORS["accent"])
    style.configure("Mono.TLabel", font=FONTS["mono"])

    # Buttons
    style.configure(
        "TButton",
        padding=(12, 6),
        font=FONTS["default"],
    )
    style.configure(
        "Accent.TButton",
        background=COLORS["accent"],
        foreground="white",
    )
    style.map(
        "Accent.TButton",
        background=[("active", "#0052a3")],
    )
    style.configure(
        "Danger.TButton",
        background=COLORS["danger"],
        foreground="white",
    )
    style.configure("Small.TButton", padding=(8, 3), font=FONTS["small"])

    # Notebook (tabs)
    style.configure(
        "TNotebook",
        background=COLORS["bg"],
        tabposition="n",
    )
    style.configure(
        "TNotebook.Tab",
        padding=(14, 6),
        font=FONTS["default"],
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLORS["bg_alt"]), ("!selected", COLORS["bg"])],
        foreground=[("selected", COLORS["accent"]), ("!selected", COLORS["fg"])],
    )

    # Treeview
    style.configure(
        "Treeview",
        font=FONTS["default"],
        rowheight=28,
        background=COLORS["bg_alt"],
        fieldbackground=COLORS["bg_alt"],
    )
    style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
    style.map(
        "Treeview",
        background=[("selected", COLORS["accent"])],
        foreground=[("selected", "white")],
    )

    # Entry
    style.configure("TEntry", padding=(6, 4))

    # LabelFrame
    style.configure("TLabelframe", background=COLORS["bg"])
    style.configure("TLabelframe.Label", background=COLORS["bg"], font=("Segoe UI", 10, "bold"))

    # Separator
    style.configure("TSeparator", background=COLORS["muted"])

    # Progressbar
    style.configure(
        "TProgressbar",
        troughcolor=COLORS["bg"],
        background=COLORS["accent"],
    )
    style.configure(
        "Success.Horizontal.TProgressbar",
        background=COLORS["success"],
    )

    # Combobox
    style.configure("TCombobox", padding=(6, 4))

    # Checkbutton
    style.configure("TCheckbutton", background=COLORS["bg"])

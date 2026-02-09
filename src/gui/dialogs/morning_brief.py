"""Morning brief dialog."""

import tkinter as tk
from tkinter import ttk
from typing import Callable

from src.core.logging import get_logger
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)


class MorningBriefDialog:
    """Morning brief display dialog.

    Shows the day's pipeline summary and a motivational message,
    then calls on_ready when the user clicks "Let's Go".
    """

    def __init__(self, parent: tk.Widget, brief_content: str, on_ready: Callable):
        self.parent = parent
        self.brief_content = brief_content
        self.on_ready = on_ready
        self._dialog: tk.Toplevel | None = None

    def show(self) -> None:
        """Display the morning brief dialog."""
        self._dialog = tk.Toplevel(self.parent)
        self._dialog.title("Morning Brief")
        self._dialog.geometry("480x340")
        self._dialog.resizable(False, False)
        self._dialog.transient(self.parent)
        self._dialog.grab_set()

        # Header
        header = tk.Frame(self._dialog, bg=COLORS["accent"], height=48)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header, text="Good morning. Here's what's on deck.",
            font=("Segoe UI", 12, "bold"), bg=COLORS["accent"], fg="white",
        ).pack(padx=16, pady=10, anchor=tk.W)

        # Content
        content = tk.Frame(self._dialog, bg=COLORS["bg_alt"])
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        tk.Label(
            content, text=self.brief_content, font=FONTS["default"],
            bg=COLORS["bg_alt"], fg=COLORS["fg"],
            justify=tk.LEFT, anchor=tk.NW, wraplength=420,
        ).pack(fill=tk.BOTH, expand=True)

        # Action
        btn_frame = tk.Frame(self._dialog, bg=COLORS["bg"])
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 16))
        ttk.Button(btn_frame, text="Let's Go", style="Accent.TButton", command=self.close).pack(
            side=tk.RIGHT,
        )

    def close(self) -> None:
        """Close dialog and start processing."""
        if self._dialog:
            self._dialog.destroy()
        self.on_ready()

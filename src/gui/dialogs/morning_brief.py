"""Morning brief dialog.

Displays the morning brief as a curtain over the Today tab.
When the user clicks 'Ready? Let's go.' it closes and the
first card is already staged behind it.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from src.core.logging import get_logger
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)


class MorningBriefDialog:
    """Morning brief display dialog."""

    def __init__(self, parent: tk.Widget, brief_content: str, on_ready: Callable):
        self.parent = parent
        self.brief_content = brief_content
        self.on_ready = on_ready
        self._dialog: Optional[tk.Toplevel] = None

    def show(self) -> None:
        """Display the morning brief dialog."""
        self._dialog = tk.Toplevel(self.parent)
        self._dialog.title("Morning Brief")
        self._dialog.geometry("600x500")
        self._dialog.transient(self.parent.winfo_toplevel())
        self._dialog.grab_set()

        main = ttk.Frame(self._dialog, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        # Header
        header = tk.Label(
            main, text="IRONLUNG 3 — MORNING BRIEF",
            font=("Segoe UI", 16, "bold"), bg=COLORS["bg"], fg=COLORS["accent"],
        )
        header.pack(pady=(0, 12))

        # Brief content in a scrollable text widget
        text_frame = ttk.Frame(main)
        text_frame.pack(fill=tk.BOTH, expand=True)

        text = tk.Text(
            text_frame, wrap=tk.WORD, font=FONTS["default"],
            bg=COLORS["bg_alt"], fg=COLORS["fg"],
            padx=16, pady=12, relief="flat",
        )
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)

        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text.insert("1.0", self.brief_content)
        text.config(state="disabled")

        # "Ready? Let's go." button
        btn = tk.Button(
            main, text="Ready?  Let's go.", font=("Segoe UI", 14, "bold"),
            bg=COLORS["accent"], fg="#ffffff", activebackground="#004c99",
            activeforeground="#ffffff", relief="flat", cursor="hand2",
            command=self.close, padx=24, pady=8,
        )
        btn.pack(pady=(16, 0))

        # Also close on Escape or Enter
        self._dialog.bind("<Return>", lambda e: self.close())
        self._dialog.bind("<Escape>", lambda e: self.close())

        logger.info("Morning brief dialog shown")

    def close(self) -> None:
        """Close dialog and start processing."""
        logger.info("Morning brief dismissed — starting processing")
        if self._dialog:
            self._dialog.destroy()
            self._dialog = None
        self.on_ready()

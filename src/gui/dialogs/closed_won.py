"""Closed won dialog for deal capture."""

import tkinter as tk
from decimal import Decimal, InvalidOperation
from tkinter import ttk
from typing import Optional

from src.core.logging import get_logger
from src.gui.theme import FONTS

logger = get_logger(__name__)


class ClosedWonDialog:
    """Deal capture dialog.

    Captures the deal value and optional notes when a prospect
    is marked as Closed/Won.
    """

    def __init__(self, parent: tk.Widget, prospect_id: int):
        self.parent = parent
        self.prospect_id = prospect_id
        self.deal_value: Optional[Decimal] = None
        self.deal_notes: Optional[str] = None
        self._captured = False
        self._dialog: Optional[tk.Toplevel] = None

    def show(self) -> bool:
        """Display dialog. Returns True if captured."""
        self._dialog = tk.Toplevel(self.parent)
        self._dialog.title("Closed Won!")
        self._dialog.geometry("420x340")
        self._dialog.resizable(False, False)
        self._dialog.transient(self.parent)
        self._dialog.grab_set()

        frame = ttk.Frame(self._dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        ttk.Label(
            frame, text="Deal Closed!", font=("Segoe UI", 14, "bold"),
        ).pack(anchor=tk.W, pady=(0, 4))

        ttk.Label(
            frame, text="Capture the deal details below.",
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(0, 16))

        # Deal value
        ttk.Label(frame, text="Deal Value ($):").pack(anchor=tk.W, pady=(0, 2))
        self._value_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self._value_var, width=20, font=FONTS["large"]).pack(
            anchor=tk.W, pady=(0, 12),
        )

        # Notes
        ttk.Label(frame, text="Notes (optional):").pack(anchor=tk.W, pady=(0, 2))
        self._notes_text = tk.Text(frame, height=5, font=FONTS["default"], wrap=tk.WORD)
        self._notes_text.pack(fill=tk.X, pady=(0, 16))

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Cancel", command=self._cancel).pack(side=tk.LEFT)
        ttk.Button(
            btn_frame, text="Capture Deal", style="Accent.TButton", command=self._capture,
        ).pack(side=tk.RIGHT)

        self._dialog.wait_window()
        return self._captured

    def _capture(self) -> None:
        """Validate and capture the deal."""
        val_str = self._value_var.get().strip().replace(",", "").replace("$", "")
        if val_str:
            try:
                self.deal_value = Decimal(val_str)
            except InvalidOperation:
                from tkinter import messagebox

                messagebox.showerror("Invalid Value", "Please enter a valid dollar amount.")
                return
        else:
            self.deal_value = Decimal("0")

        notes = self._notes_text.get("1.0", tk.END).strip()
        self.deal_notes = notes or None

        self._captured = True
        logger.info(
            "Deal captured",
            extra={
                "context": {
                    "prospect_id": self.prospect_id,
                    "value": str(self.deal_value),
                }
            },
        )
        if self._dialog:
            self._dialog.destroy()

    def _cancel(self) -> None:
        self._captured = False
        if self._dialog:
            self._dialog.destroy()

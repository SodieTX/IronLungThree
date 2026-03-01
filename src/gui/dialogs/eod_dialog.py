"""End-of-day summary dialog.

Shows Jeff his daily stats when he's done grinding.
Triggered by: queue empty OR app close OR manual (Ctrl+E).
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from src.content.eod_summary import generate_eod_summary
from src.core.logging import get_logger
from src.db.database import Database
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)


class EODSummaryDialog:
    """End-of-day summary popup."""

    def __init__(self, parent: tk.Misc, db: Database):
        self.parent = parent
        self.db = db
        self._dialog: Optional[tk.Toplevel] = None

    def show(self) -> None:
        """Generate and display the EOD summary."""
        try:
            summary = generate_eod_summary(self.db)
        except Exception as e:
            logger.error(f"Failed to generate EOD summary: {e}")
            return

        self._dialog = tk.Toplevel(self.parent)
        self._dialog.title("End of Day — IronLung 3")
        self._dialog.geometry("520x600")
        self._dialog.configure(bg=COLORS["bg"])
        self._dialog.transient(self.parent.winfo_toplevel())
        self._dialog.grab_set()

        # Center on parent
        self._dialog.update_idletasks()
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() - 520) // 2
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() - 600) // 2
        self._dialog.geometry(f"+{x}+{y}")

        # Header
        header = tk.Frame(self._dialog, bg=COLORS["accent"], height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header,
            text="END OF DAY",
            font=("Segoe UI", 16, "bold"),
            bg=COLORS["accent"],
            fg="#ffffff",
        ).pack(expand=True)

        # Date
        tk.Label(
            self._dialog,
            text=summary.date,
            font=("Segoe UI", 11),
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).pack(pady=(12, 8))

        # Stats grid
        stats_frame = tk.Frame(self._dialog, bg=COLORS["bg"])
        stats_frame.pack(fill=tk.X, padx=24, pady=8)

        stats = [
            ("Cards Worked", str(summary.cards_processed)),
            ("Calls Made", str(summary.calls_made)),
            ("Emails Sent", str(summary.emails_sent)),
            ("Demos Scheduled", str(summary.demos_scheduled)),
            ("Deals Closed", str(summary.deals_closed)),
            ("Pipeline Moves", str(summary.status_changes)),
        ]

        for i, (label, value) in enumerate(stats):
            row = i // 2
            col = i % 2

            cell = tk.Frame(stats_frame, bg=COLORS["bg_alt"], bd=1, relief="solid")
            cell.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
            stats_frame.columnconfigure(col, weight=1)

            tk.Label(
                cell,
                text=value,
                font=("Segoe UI", 24, "bold"),
                bg=COLORS["bg_alt"],
                fg=COLORS["accent"] if int(value) > 0 else COLORS["muted"],
            ).pack(pady=(8, 0))

            tk.Label(
                cell,
                text=label,
                font=FONTS["small"],
                bg=COLORS["bg_alt"],
                fg=COLORS["muted"],
            ).pack(pady=(0, 8))

        # Tomorrow preview
        tk.Label(
            self._dialog,
            text="TOMORROW",
            font=("Segoe UI", 11, "bold"),
            bg=COLORS["bg"],
            fg=COLORS["fg"],
        ).pack(pady=(16, 4))

        tk.Label(
            self._dialog,
            text=summary.tomorrow_preview,
            font=("Segoe UI", 10),
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).pack()

        # Motivational closer
        if summary.cards_processed >= 20:
            closer = "Strong day. Rest up."
        elif summary.cards_processed > 0:
            closer = "Good work. See you tomorrow."
        else:
            closer = "Tomorrow is a new day."

        tk.Label(
            self._dialog,
            text=closer,
            font=("Segoe UI", 12, "italic"),
            bg=COLORS["bg"],
            fg=COLORS["accent"],
        ).pack(pady=(20, 8))

        # Close button
        ttk.Button(
            self._dialog,
            text="Done",
            command=self._close,
        ).pack(pady=(8, 16))

        self._dialog.bind("<Escape>", lambda e: self._close())
        self._dialog.bind("<Return>", lambda e: self._close())

    def _close(self) -> None:
        """Close the dialog."""
        if self._dialog is not None:
            self._dialog.destroy()

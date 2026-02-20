"""Email recall dialog - The "Oh Shit" button.

Attempts to recall/retract a sent email. Shows progress and result
to the user.
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Optional

from src.core.logging import get_logger
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)


class EmailRecallDialog:
    """Email recall attempt dialog."""

    def __init__(
        self,
        parent: tk.Widget,
        message_id: str,
        outlook: Optional[Any] = None,
    ):
        self.parent = parent
        self.message_id = message_id
        self.outlook = outlook
        self._dialog: Optional[tk.Toplevel] = None
        self._status_label: Optional[tk.Label] = None
        self._follow_up_var = tk.BooleanVar(value=True)
        self._custom_text: Optional[tk.Text] = None

    def show(self) -> None:
        """Display the recall dialog."""
        self._dialog = tk.Toplevel(self.parent)
        self._dialog.title("Recall Email")
        self._dialog.geometry("460x360")
        self._dialog.transient(self.parent.winfo_toplevel())
        self._dialog.grab_set()

        main = ttk.Frame(self._dialog, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        # Header
        tk.Label(
            main,
            text="RECALL EMAIL",
            font=("Segoe UI", 14, "bold"),
            fg=COLORS["danger"],
        ).pack(pady=(0, 8))

        tk.Label(
            main,
            text=(
                "This will attempt to delete the sent message and\n"
                "optionally send a 'please disregard' follow-up."
            ),
            font=FONTS["small"],
            fg=COLORS["muted"],
            justify="center",
        ).pack(pady=(0, 12))

        # Options
        ttk.Checkbutton(
            main,
            text="Send 'please disregard' follow-up",
            variable=self._follow_up_var,
        ).pack(anchor="w", padx=8, pady=(0, 4))

        # Custom follow-up text
        ttk.Label(main, text="Custom follow-up text (optional):").pack(
            anchor="w", padx=8, pady=(4, 2)
        )
        self._custom_text = tk.Text(main, height=3, width=40, font=FONTS["small"])
        self._custom_text.pack(fill=tk.X, padx=8, pady=(0, 8))

        # Status / result area
        self._status_label = tk.Label(
            main,
            text="",
            font=FONTS["default"],
            fg=COLORS["fg"],
            wraplength=400,
        )
        self._status_label.pack(fill=tk.X, padx=8, pady=(0, 8))

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(pady=4)
        ttk.Button(btn_frame, text="Recall Now", command=self._on_recall).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(
            side=tk.LEFT, padx=8
        )

        self._dialog.bind("<Escape>", lambda e: self._on_cancel())
        self._dialog.wait_window()

    def _on_recall(self) -> None:
        """Execute the recall attempt."""
        if not self._status_label:
            return

        if not self.outlook:
            self._status_label.config(
                text="Outlook not connected. Cannot recall email.",
                fg=COLORS["danger"],
            )
            return

        self._status_label.config(text="Attempting recall...", fg=COLORS["fg"])
        if self._dialog:
            self._dialog.update()

        # Get custom follow-up text
        custom_text = None
        if self._custom_text:
            text = self._custom_text.get("1.0", tk.END).strip()
            if text:
                custom_text = text

        try:
            from src.engine.email_recall import attempt_recall

            result = attempt_recall(
                outlook=self.outlook,
                message_id=self.message_id,
                send_follow_up=self._follow_up_var.get(),
                follow_up_text=custom_text,
            )

            if result.success:
                self._status_label.config(
                    text=result.message,
                    fg=COLORS["success"],
                )
                logger.info(
                    f"Email recall succeeded: {result.method}",
                    extra={"context": {"message_id": self.message_id}},
                )
            else:
                self._status_label.config(
                    text=result.message,
                    fg=COLORS["danger"],
                )
                logger.warning(
                    f"Email recall failed: {result.message}",
                    extra={"context": {"message_id": self.message_id}},
                )

        except Exception as e:
            logger.error(f"Email recall error: {e}")
            self._status_label.config(
                text=f"Error: {e}",
                fg=COLORS["danger"],
            )

    def _on_cancel(self) -> None:
        """Cancel dialog."""
        if self._dialog:
            self._dialog.destroy()

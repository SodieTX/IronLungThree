"""Email recall dialog - The "Oh Shit" button."""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


class EmailRecallDialog:
    """Email recall attempt dialog.

    Shows a progress indicator while attempting to recall an email
    via the Outlook integration. Displays the result (success/fail).
    """

    def __init__(self, parent: tk.Widget, message_id: str):
        self.parent = parent
        self.message_id = message_id
        self._dialog: Optional[tk.Toplevel] = None
        self._status_var: Optional[tk.StringVar] = None

    def show(self) -> None:
        """Display dialog and attempt recall."""
        self._dialog = tk.Toplevel(self.parent)
        self._dialog.title("Recall Email")
        self._dialog.geometry("400x220")
        self._dialog.resizable(False, False)
        self._dialog.transient(self.parent)
        self._dialog.grab_set()

        frame = ttk.Frame(self._dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        ttk.Label(
            frame, text="Email Recall", font=("Segoe UI", 12, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))

        msg_preview = self.message_id[:40] + "..." if len(self.message_id) > 40 else self.message_id
        ttk.Label(
            frame,
            text=f"Attempting to recall message:\n{msg_preview}",
            style="Muted.TLabel", wraplength=360,
        ).pack(anchor=tk.W, pady=(0, 12))

        # Progress
        self._progress = ttk.Progressbar(frame, mode="indeterminate", length=350)
        self._progress.pack(fill=tk.X, pady=(0, 8))

        self._status_var = tk.StringVar(value="Attempting recall...")
        ttk.Label(frame, textvariable=self._status_var).pack(anchor=tk.W, pady=(0, 12))

        # Close button (enabled after attempt completes)
        self._close_btn = ttk.Button(frame, text="Close", command=self._close, state=tk.DISABLED)
        self._close_btn.pack(anchor=tk.E)

        # Start recall attempt
        self._progress.start(20)
        self._dialog.after(500, self._attempt_recall)

    def _attempt_recall(self) -> None:
        """Attempt the email recall via Outlook integration."""
        try:
            from src.integrations.outlook import OutlookClient

            client = OutlookClient()
            success = client.recall_message(self.message_id)
            self._progress.stop()

            if success:
                self._status_var.set("Recall request sent successfully.")
                logger.info(
                    "Email recall succeeded",
                    extra={"context": {"message_id": self.message_id}},
                )
            else:
                self._status_var.set("Recall failed — message may already have been read.")
                logger.warning(
                    "Email recall failed",
                    extra={"context": {"message_id": self.message_id}},
                )
        except Exception as e:
            self._progress.stop()
            self._status_var.set(f"Recall error: {e}")
            logger.error(
                "Email recall error", extra={"context": {"error": str(e)}},
            )

        self._close_btn.configure(state=tk.NORMAL)

    def _close(self) -> None:
        if self._dialog:
            self._dialog.destroy()

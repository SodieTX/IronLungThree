"""Nurture email approval queue dialog.

Jeff reviews AI-drafted nurture emails here.
Approve, reject, or edit before sending.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.engine.nurture import NurtureEmail, NurtureEngine
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)


class NurtureQueueDialog:
    """Nurture email review and approval dialog."""

    def __init__(self, parent: tk.Widget, db: Database):
        self.parent = parent
        self.db = db
        self._engine = NurtureEngine(db)
        self._dialog: Optional[tk.Toplevel] = None
        self._pending: list[NurtureEmail] = []
        self._current_index: int = 0
        self._subject_var = tk.StringVar()
        self._body_text: Optional[scrolledtext.ScrolledText] = None
        self._counter_label: Optional[tk.Label] = None
        self._info_label: Optional[tk.Label] = None
        self._seq_label: Optional[tk.Label] = None

    def show(self) -> None:
        """Open the nurture approval queue."""
        self._pending = self._engine.get_pending_approval()

        self._dialog = tk.Toplevel(self.parent)
        self._dialog.title("Nurture Email Queue — IronLung 3")
        self._dialog.geometry("700x650")
        self._dialog.configure(bg=COLORS["bg"])
        self._dialog.transient(self.parent)
        self._dialog.grab_set()

        # Center on parent
        self._dialog.update_idletasks()
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() - 700) // 2
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() - 650) // 2
        self._dialog.geometry(f"+{x}+{y}")

        self._build_ui()
        self._show_current_email()

        self._dialog.bind("<Escape>", lambda e: self._dialog.destroy())

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        if not self._dialog:
            return

        # Header bar
        header = tk.Frame(self._dialog, bg=COLORS["accent"], height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="NURTURE EMAIL QUEUE",
            font=("Segoe UI", 14, "bold"),
            bg=COLORS["accent"],
            fg="#ffffff",
        ).pack(side=tk.LEFT, padx=16)

        self._counter_label = tk.Label(
            header,
            text="",
            font=("Segoe UI", 11),
            bg=COLORS["accent"],
            fg="#ffffff",
        )
        self._counter_label.pack(side=tk.RIGHT, padx=16)

        # Prospect info
        self._info_label = tk.Label(
            self._dialog,
            text="",
            font=("Segoe UI", 11, "bold"),
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            anchor="w",
        )
        self._info_label.pack(fill=tk.X, padx=16, pady=(12, 4))

        # Sequence badge
        self._seq_label = tk.Label(
            self._dialog,
            text="",
            font=FONTS["small"],
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            anchor="w",
        )
        self._seq_label.pack(fill=tk.X, padx=16, pady=(0, 8))

        # Subject (editable)
        subj_frame = tk.Frame(self._dialog, bg=COLORS["bg"])
        subj_frame.pack(fill=tk.X, padx=16, pady=(0, 4))
        tk.Label(
            subj_frame,
            text="Subject:",
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["bg"],
            fg=COLORS["fg"],
        ).pack(side=tk.LEFT)
        ttk.Entry(
            subj_frame,
            textvariable=self._subject_var,
            font=("Segoe UI", 10),
            width=60,
        ).pack(side=tk.LEFT, padx=(8, 0), fill=tk.X, expand=True)

        # Body (editable)
        tk.Label(
            self._dialog,
            text="Body:",
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            anchor="w",
        ).pack(fill=tk.X, padx=16)

        self._body_text = scrolledtext.ScrolledText(
            self._dialog,
            font=("Segoe UI", 10),
            wrap=tk.WORD,
            height=16,
            bg=COLORS["bg_alt"],
            fg=COLORS["fg"],
            insertbackground=COLORS["fg"],
        )
        self._body_text.pack(fill=tk.BOTH, expand=True, padx=16, pady=(4, 8))

        # Action buttons
        btn_frame = tk.Frame(self._dialog, bg=COLORS["bg"])
        btn_frame.pack(fill=tk.X, padx=16, pady=(0, 8))

        ttk.Button(
            btn_frame,
            text="Approve",
            command=self._on_approve,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            btn_frame,
            text="Approve All",
            command=self._on_approve_all,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            btn_frame,
            text="Reject",
            command=self._on_reject,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            btn_frame,
            text="Skip",
            command=self._on_skip,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            btn_frame,
            text="Close",
            command=self._dialog.destroy,
        ).pack(side=tk.RIGHT)

        # Navigation
        nav_frame = tk.Frame(self._dialog, bg=COLORS["bg"])
        nav_frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        ttk.Button(nav_frame, text="Prev", command=self._prev_email).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(nav_frame, text="Next", command=self._next_email).pack(
            side=tk.LEFT
        )

    def _show_current_email(self) -> None:
        """Display the current email in the review pane."""
        if not self._pending:
            self._show_empty_state()
            return

        if self._current_index >= len(self._pending):
            self._current_index = len(self._pending) - 1
        if self._current_index < 0:
            self._current_index = 0

        email = self._pending[self._current_index]

        if self._counter_label:
            self._counter_label.config(
                text=f"{self._current_index + 1} of {len(self._pending)} pending"
            )

        if self._info_label:
            self._info_label.config(
                text=f"{email.prospect_name} — {email.company_name}"
            )

        if self._seq_label:
            seq_display = email.sequence.value.replace("_", " ").title()
            self._seq_label.config(
                text=f"{seq_display} | Step {email.sequence_step} | To: {email.to_address}"
            )

        self._subject_var.set(email.subject)

        if self._body_text:
            self._body_text.delete("1.0", tk.END)
            self._body_text.insert("1.0", email.body)

    def _show_empty_state(self) -> None:
        """Show when queue is empty."""
        if self._counter_label:
            self._counter_label.config(text="0 pending")
        if self._info_label:
            self._info_label.config(text="No nurture emails pending approval.")
        if self._seq_label:
            self._seq_label.config(text="")
        self._subject_var.set("")
        if self._body_text:
            self._body_text.delete("1.0", tk.END)

    def _save_edits(self, email: NurtureEmail) -> None:
        """Save any edits Jeff made to subject/body back to the queue."""
        new_subject = self._subject_var.get().strip()
        new_body = self._body_text.get("1.0", tk.END).strip() if self._body_text else ""

        if new_subject != email.subject or new_body != email.body:
            try:
                conn = self.db._get_connection()
                conn.execute(
                    """UPDATE nurture_queue
                       SET subject = ?, body = ?
                       WHERE id = ?""",
                    (new_subject, new_body, email.id),
                )
                conn.commit()
                email.subject = new_subject
                email.body = new_body
            except Exception as e:
                logger.warning(f"Failed to save nurture email edits: {e}")

    def _on_approve(self) -> None:
        """Approve the current email."""
        if not self._pending:
            return
        email = self._pending[self._current_index]
        self._save_edits(email)
        self._engine.approve_email(email.id)
        self._pending.pop(self._current_index)
        if self._current_index >= len(self._pending):
            self._current_index = max(0, len(self._pending) - 1)
        self._show_current_email()

    def _on_approve_all(self) -> None:
        """Approve all remaining pending emails."""
        if not self._pending:
            return
        count = len(self._pending)
        parent = self._dialog if self._dialog else self.parent
        confirm = messagebox.askyesno(
            "Approve All",
            f"Approve all {count} pending nurture emails?",
            parent=parent,
        )
        if not confirm:
            return
        for email in self._pending:
            self._engine.approve_email(email.id)
        self._pending.clear()
        self._current_index = 0
        self._show_current_email()

    def _on_reject(self) -> None:
        """Reject the current email."""
        if not self._pending:
            return
        email = self._pending[self._current_index]
        self._engine.reject_email(email.id, reason="Rejected during review")
        self._pending.pop(self._current_index)
        if self._current_index >= len(self._pending):
            self._current_index = max(0, len(self._pending) - 1)
        self._show_current_email()

    def _on_skip(self) -> None:
        """Skip to next email without action."""
        self._next_email()

    def _prev_email(self) -> None:
        """Navigate to previous email."""
        if self._current_index > 0:
            self._current_index -= 1
            self._show_current_email()

    def _next_email(self) -> None:
        """Navigate to next email."""
        if self._current_index < len(self._pending) - 1:
            self._current_index += 1
            self._show_current_email()

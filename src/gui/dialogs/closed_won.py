"""Closed won dialog for deal capture.

Captures deal value, close date, and notes when Jeff dispositions
a prospect as WON. Calculates commission and logs the activity.
"""

import tkinter as tk
from datetime import date
from decimal import Decimal, InvalidOperation
from tkinter import messagebox, ttk
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityOutcome,
    ActivityType,
    Population,
)
from src.gui.theme import FONTS

logger = get_logger(__name__)

# Default commission rate
DEFAULT_COMMISSION_RATE = Decimal("0.06")


class ClosedWonDialog:
    """Deal capture dialog for closed-won prospects."""

    def __init__(self, parent: tk.Widget, prospect_id: int, db: Optional[Database] = None):
        self.parent = parent
        self.prospect_id = prospect_id
        self.db = db
        self.deal_value: Optional[Decimal] = None
        self.close_date: Optional[date] = None
        self.close_notes: Optional[str] = None
        self._dialog: Optional[tk.Toplevel] = None
        self._value_var = tk.StringVar()
        self._date_var = tk.StringVar(value=date.today().isoformat())
        self._notes_text: Optional[tk.Text] = None
        self._commission_label: Optional[tk.Label] = None
        self._captured = False

    def show(self) -> bool:
        """Display dialog. Returns True if deal was captured."""
        self._dialog = tk.Toplevel(self.parent)
        self._dialog.title("Closed Won — Deal Capture")
        self._dialog.geometry("400x380")
        self._dialog.transient(self.parent.winfo_toplevel())
        self._dialog.grab_set()

        main = ttk.Frame(self._dialog, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        # Header
        tk.Label(
            main,
            text="Deal Closed!",
            font=("Segoe UI", 14, "bold"),
            fg="#28a745",
        ).pack(pady=(0, 12))

        # Deal value
        ttk.Label(main, text="Deal Value ($):", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 4)
        )
        value_entry = ttk.Entry(main, textvariable=self._value_var, width=20)
        value_entry.pack(anchor="w", padx=4, pady=(0, 4))
        value_entry.focus_set()

        # Bind value change to update commission display
        self._value_var.trace_add("write", self._update_commission)

        # Commission display
        self._commission_label = tk.Label(
            main,
            text="Commission (6%): $0.00",
            font=FONTS["small"],
            fg="#6c757d",
        )
        self._commission_label.pack(anchor="w", padx=4, pady=(0, 8))

        # Close date
        ttk.Label(main, text="Close Date:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 4)
        )
        ttk.Entry(main, textvariable=self._date_var, width=14).pack(anchor="w", padx=4, pady=(0, 8))

        # Notes
        ttk.Label(main, text="Notes:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 4))
        self._notes_text = tk.Text(main, height=4, width=40, font=FONTS["small"])
        self._notes_text.pack(fill=tk.X, padx=4, pady=(0, 12))

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(pady=4)
        ttk.Button(btn_frame, text="Save Deal", command=self._on_save).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side=tk.LEFT, padx=8)

        self._dialog.bind("<Return>", lambda e: self._on_save())
        self._dialog.bind("<Escape>", lambda e: self._on_cancel())

        self._dialog.wait_window()
        return self._captured

    def _update_commission(self, *args: object) -> None:
        """Update commission display when deal value changes."""
        if not self._commission_label:
            return
        try:
            value = Decimal(self._value_var.get().replace(",", ""))
            commission = value * DEFAULT_COMMISSION_RATE
            rate_pct = int(DEFAULT_COMMISSION_RATE * 100)
            self._commission_label.config(text=f"Commission ({rate_pct}%): ${commission:,.2f}")
        except (InvalidOperation, ValueError):
            self._commission_label.config(text="Commission (6%): $0.00")

    def _on_save(self) -> None:
        """Save the deal."""
        # Validate deal value
        try:
            value_str = self._value_var.get().strip().replace(",", "")
            if not value_str:
                parent = self._dialog if self._dialog else self.parent.winfo_toplevel()
                messagebox.showwarning("Missing Value", "Enter a deal value.", parent=parent)
                return
            self.deal_value = Decimal(value_str)
        except (InvalidOperation, ValueError):
            parent = self._dialog if self._dialog else self.parent.winfo_toplevel()
            messagebox.showwarning("Invalid Value", "Enter a valid number.", parent=parent)
            return

        # Validate close date
        date_str = self._date_var.get().strip()
        try:
            self.close_date = date.fromisoformat(date_str)
        except ValueError:
            parent = self._dialog if self._dialog else self.parent.winfo_toplevel()
            messagebox.showwarning("Invalid Date", "Use YYYY-MM-DD format.", parent=parent)
            return

        # Get notes
        self.close_notes = self._notes_text.get("1.0", tk.END).strip() if self._notes_text else None

        # Save to database
        if self.db:
            prospect = self.db.get_prospect(self.prospect_id)
            if prospect:
                prev_population = prospect.population
                prospect.population = Population.CLOSED_WON
                prospect.deal_value = self.deal_value
                prospect.close_date = self.close_date
                prospect.close_notes = self.close_notes or None
                self.db.update_prospect(prospect)

                # Log activity
                commission = self.deal_value * DEFAULT_COMMISSION_RATE
                activity = Activity(
                    prospect_id=self.prospect_id,
                    activity_type=ActivityType.STATUS_CHANGE,
                    outcome=ActivityOutcome.CLOSED_WON,
                    population_before=prev_population,
                    population_after=Population.CLOSED_WON,
                    notes=(
                        f"Deal closed: ${self.deal_value:,.2f} | "
                        f"Commission: ${commission:,.2f} | "
                        f"{self.close_notes or ''}"
                    ),
                    created_by="user",
                )
                self.db.create_activity(activity)

                logger.info(
                    f"Deal captured for prospect {self.prospect_id}: ${self.deal_value:,.2f}",
                    extra={
                        "context": {
                            "prospect_id": self.prospect_id,
                            "deal_value": str(self.deal_value),
                            "close_date": str(self.close_date),
                        }
                    },
                )

        self._captured = True

        # After saving, offer to generate a contract
        self._show_contract_option()

    def _show_contract_option(self) -> None:
        """Show contract generation option after deal is saved."""
        if not self._dialog or not self.db:
            if self._dialog:
                self._dialog.destroy()
            return

        # Clear the dialog and show contract option
        for widget in self._dialog.winfo_children():
            widget.destroy()

        self._dialog.geometry("400x200")
        main = ttk.Frame(self._dialog, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            main,
            text="Deal Saved!",
            font=("Segoe UI", 14, "bold"),
            fg="#28a745",
        ).pack(pady=(0, 12))

        tk.Label(
            main,
            text="Would you like to generate a contract?",
            font=("Segoe UI", 10),
        ).pack(pady=(0, 16))

        btn_frame = ttk.Frame(main)
        btn_frame.pack(pady=4)
        ttk.Button(btn_frame, text="Generate Contract", command=self._on_generate_contract).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(btn_frame, text="Done", command=self._on_cancel).pack(side=tk.LEFT, padx=8)

    def _on_generate_contract(self) -> None:
        """Generate and display a contract."""
        if not self.db or not self._dialog:
            return

        try:
            from src.engine.contract_gen import render_contract

            contract = render_contract(self.db, self.prospect_id)

            # Show contract in a new window
            preview = tk.Toplevel(self._dialog)
            preview.title(f"Contract — {contract.prospect_name}")
            preview.geometry("700x600")

            text_frame = ttk.Frame(preview, padding=8)
            text_frame.pack(fill=tk.BOTH, expand=True)

            text_widget = tk.Text(text_frame, wrap=tk.WORD, font=("Courier New", 10))
            scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)

            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            text_widget.insert("1.0", contract.content)

            # Copy and close buttons
            btn_frame = ttk.Frame(preview, padding=8)
            btn_frame.pack(fill=tk.X)

            def copy_to_clipboard() -> None:
                preview.clipboard_clear()
                preview.clipboard_append(contract.content)
                messagebox.showinfo("Copied", "Contract copied to clipboard.", parent=preview)

            ttk.Button(btn_frame, text="Copy to Clipboard", command=copy_to_clipboard).pack(
                side=tk.LEFT, padx=8
            )
            ttk.Button(btn_frame, text="Close", command=preview.destroy).pack(side=tk.LEFT, padx=8)

        except FileNotFoundError:
            parent = self._dialog if self._dialog else self.parent.winfo_toplevel()
            messagebox.showwarning(
                "Template Missing",
                "No contract template found.\n\n"
                "Create one at: templates/contracts/nexys_standard.txt.j2",
                parent=parent,
            )
        except Exception as e:
            parent = self._dialog if self._dialog else self.parent.winfo_toplevel()
            messagebox.showerror("Error", f"Failed to generate contract: {e}", parent=parent)

        # Close the closed-won dialog
        if self._dialog:
            self._dialog.destroy()

    def _on_cancel(self) -> None:
        """Cancel dialog."""
        if self._dialog:
            self._dialog.destroy()

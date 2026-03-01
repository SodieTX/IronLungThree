"""Contact method add dialog."""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from src.core.phone import normalize_phone
from src.db.models import ContactMethod, ContactMethodType


class ContactMethodDialog:
    """Dialog for adding a contact method (email or phone)."""

    def __init__(self, parent: tk.Widget, prospect_id: int, existing_methods: list[ContactMethod]):
        self.parent = parent
        self.prospect_id = prospect_id
        self.existing_methods = existing_methods
        self._dialog: Optional[tk.Toplevel] = None
        self._saved = False
        self.method: Optional[ContactMethod] = None

        self._type_var = tk.StringVar(value="email")
        self._value_var = tk.StringVar()
        self._label_var = tk.StringVar()
        self._primary_var = tk.BooleanVar(value=True)
        self._verified_var = tk.BooleanVar(value=False)

    def show(self) -> Optional[ContactMethod]:
        """Show the dialog and return ContactMethod if saved."""
        self._dialog = tk.Toplevel(self.parent)
        self._dialog.title("Add Contact Method")
        self._dialog.geometry("420x260")
        self._dialog.transient(self.parent.winfo_toplevel())
        self._dialog.grab_set()

        main = ttk.Frame(self._dialog, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        # Type
        ttk.Label(main, text="Type:", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="e", padx=4, pady=6
        )
        type_combo = ttk.Combobox(
            main,
            textvariable=self._type_var,
            values=["email", "phone"],
            state="readonly",
            width=18,
        )
        type_combo.grid(row=0, column=1, sticky="w", padx=4, pady=6)
        self._type_var.trace_add("write", lambda *_: self._update_primary_default())

        # Value
        ttk.Label(main, text="Value:", font=("Segoe UI", 10, "bold")).grid(
            row=1, column=0, sticky="e", padx=4, pady=6
        )
        ttk.Entry(main, textvariable=self._value_var, width=28).grid(
            row=1, column=1, sticky="w", padx=4, pady=6
        )

        # Label
        ttk.Label(main, text="Label:", font=("Segoe UI", 10, "bold")).grid(
            row=2, column=0, sticky="e", padx=4, pady=6
        )
        ttk.Entry(main, textvariable=self._label_var, width=28).grid(
            row=2, column=1, sticky="w", padx=4, pady=6
        )

        # Primary / verified
        ttk.Checkbutton(main, text="Set as primary", variable=self._primary_var).grid(
            row=3, column=1, sticky="w", padx=4, pady=4
        )
        ttk.Checkbutton(main, text="Verified", variable=self._verified_var).grid(
            row=4, column=1, sticky="w", padx=4, pady=4
        )

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=12)
        ttk.Button(btn_frame, text="Add", command=self._on_save).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side=tk.LEFT, padx=8)

        self._update_primary_default()
        self._dialog.wait_window()

        return self.method if self._saved else None

    def _update_primary_default(self) -> None:
        """Default primary to True if none exists for type."""
        method_type = self._type_var.get()
        has_primary = any(
            m.type and m.type.value == method_type and m.is_primary for m in self.existing_methods
        )
        self._primary_var.set(not has_primary)

    def _on_save(self) -> None:
        """Validate and save."""
        if not self._dialog:
            return

        method_type = self._type_var.get().strip().lower()
        value = self._value_var.get().strip()
        label = self._label_var.get().strip() or None

        if not value:
            messagebox.showwarning("Validation", "Value is required.", parent=self._dialog)
            return

        if method_type == "email":
            if "@" not in value or "." not in value:
                messagebox.showwarning(
                    "Validation", "Enter a valid email address.", parent=self._dialog
                )
                return
            value = value.lower()
            existing = {m.value.lower() for m in self.existing_methods if m.type.value == "email"}
            if value in existing:
                messagebox.showwarning(
                    "Duplicate", "That email already exists.", parent=self._dialog
                )
                return
            method_enum = ContactMethodType.EMAIL
        elif method_type == "phone":
            digits = normalize_phone(value)
            if len(digits) < 7:
                messagebox.showwarning(
                    "Validation", "Enter a valid phone number.", parent=self._dialog
                )
                return
            existing = {
                normalize_phone(m.value) for m in self.existing_methods if m.type.value == "phone"
            }
            if digits in existing:
                messagebox.showwarning(
                    "Duplicate", "That phone already exists.", parent=self._dialog
                )
                return
            value = digits
            method_enum = ContactMethodType.PHONE
        else:
            messagebox.showwarning("Validation", "Select a valid type.", parent=self._dialog)
            return

        self.method = ContactMethod(
            prospect_id=self.prospect_id,
            type=method_enum,
            value=value,
            label=label,
            is_primary=self._primary_var.get(),
            is_verified=self._verified_var.get(),
            source="manual",
        )
        self._saved = True
        self._dialog.destroy()

    def _on_cancel(self) -> None:
        """Close dialog without saving."""
        if self._dialog:
            self._dialog.destroy()

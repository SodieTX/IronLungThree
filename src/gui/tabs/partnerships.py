"""Partnerships tab - Non-prospect relationship contacts.

Step 7.9: Partnership contact management and promotion workflow.
Allows viewing partnership contacts and promoting them to prospect status.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Population
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class PartnershipsTab(TabBase):
    """Partnership contacts management.

    Displays contacts in the PARTNERSHIP population and allows:
    - Viewing partner contact details
    - Promoting partners to unengaged/engaged prospects
    - Adding notes to partner records
    """

    def __init__(self, parent: tk.Widget, db: Database):
        super().__init__(parent, db)
        self._partners: list = []
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the partnerships tab UI."""
        self.frame = ttk.Frame(self.parent)

        # Header
        header = ttk.Frame(self.frame)
        header.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(header, text="Partnerships", font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header)
        btn_frame.pack(side=tk.RIGHT)

        ttk.Button(
            btn_frame, text="Promote to Prospect", command=self._promote_selected
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh).pack(side=tk.LEFT)

        # Separator
        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)

        # Partner list (Treeview)
        tree_frame = ttk.Frame(self.frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("name", "company", "title", "score", "notes")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self._tree.heading("name", text="Name")
        self._tree.heading("company", text="Company")
        self._tree.heading("title", text="Title")
        self._tree.heading("score", text="Score")
        self._tree.heading("notes", text="Notes")

        self._tree.column("name", width=150)
        self._tree.column("company", width=150)
        self._tree.column("title", width=120)
        self._tree.column("score", width=60)
        self._tree.column("notes", width=300)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)

        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Status bar
        self._status_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self._status_var, font=("Segoe UI", 9)).pack(
            fill=tk.X, padx=10, pady=(0, 10)
        )

    def refresh(self) -> None:
        """Reload partnership contacts from database."""
        self._partners = self.db.get_prospects(population=Population.PARTNERSHIP, limit=500)

        # Clear tree
        for item in self._tree.get_children():
            self._tree.delete(item)

        # Populate
        for p in self._partners:
            company = self.db.get_company(p.company_id)
            company_name = company.name if company else "Unknown"
            notes_preview = (p.notes[:80] + "...") if p.notes and len(p.notes) > 80 else (p.notes or "")

            self._tree.insert(
                "",
                tk.END,
                iid=str(p.id),
                values=(p.full_name, company_name, p.title or "", p.prospect_score, notes_preview),
            )

        self._status_var.set(f"{len(self._partners)} partnership contacts")

        logger.debug(
            "Partnerships tab refreshed",
            extra={"context": {"count": len(self._partners)}},
        )

    def on_activate(self) -> None:
        """Called when tab becomes visible."""
        self.refresh()

    def _promote_selected(self) -> None:
        """Promote selected partner to prospect (unengaged population)."""
        selected = self._tree.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Select a partner to promote.")
            return

        prospect_id = int(selected[0])
        prospect = self.db.get_prospect(prospect_id)
        if not prospect:
            return

        confirm = messagebox.askyesno(
            "Promote Partner",
            f"Promote {prospect.full_name} from Partnership to Unengaged?\n"
            f"This will add them to the sales pipeline.",
        )
        if not confirm:
            return

        from src.engine.populations import can_transition, transition_prospect

        if not can_transition(Population.PARTNERSHIP, Population.UNENGAGED):
            messagebox.showerror("Error", "Cannot transition from Partnership to Unengaged.")
            return

        try:
            transition_prospect(
                self.db,
                prospect_id,
                Population.UNENGAGED,
                reason="Promoted from partnership to prospect",
            )
            self.refresh()
            self._status_var.set(f"Promoted {prospect.full_name} to Unengaged pipeline")
            logger.info(
                "Partner promoted to prospect",
                extra={"context": {"prospect_id": prospect_id, "name": prospect.full_name}},
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to promote: {e}")

"""Broken tab - Records missing phone/email."""

import tkinter as tk
from tkinter import ttk

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Population, Prospect, ResearchStatus
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class BrokenTab(TabBase):
    """Broken prospects management.

    Shows records missing phone and/or email, grouped by research status.
    """

    def __init__(self, parent: tk.Widget, db: Database):
        super().__init__(parent, db)
        self._prospects: list[Prospect] = []
        self._build_ui()

    def _build_ui(self) -> None:
        self.frame = ttk.Frame(self.parent)  # type: ignore[assignment]

        # --- Header ---
        header = ttk.Frame(self.frame)
        header.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(header, text="Broken Records", font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Needs Confirm", command=self.show_needs_confirmation,
                   style="Small.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="In Progress", command=self.show_in_progress,
                   style="Small.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Manual Needed", command=self.show_manual_needed,
                   style="Small.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh).pack(side=tk.LEFT, padx=2)

        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)

        # --- Treeview ---
        tree_frame = ttk.Frame(self.frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("name", "company", "research", "confidence", "notes")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        self._tree.heading("name", text="Name")
        self._tree.heading("company", text="Company")
        self._tree.heading("research", text="Research Status")
        self._tree.heading("confidence", text="Confidence")
        self._tree.heading("notes", text="Notes")
        self._tree.column("name", width=150)
        self._tree.column("company", width=150)
        self._tree.column("research", width=120)
        self._tree.column("confidence", width=80)
        self._tree.column("notes", width=300)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Status
        self._status_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self._status_var, style="Muted.TLabel").pack(
            fill=tk.X, padx=10, pady=(0, 10),
        )

    # ------------------------------------------------------------------
    # TabBase
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        try:
            self._prospects = self.db.get_prospects(
                population=Population.BROKEN, sort_by="data_confidence", sort_dir="ASC", limit=500,
            )
        except Exception as e:
            logger.error("Broken tab query failed", extra={"context": {"error": str(e)}})
            self._prospects = []
        self._populate_tree(self._prospects)

    def on_activate(self) -> None:
        self.refresh()

    # ------------------------------------------------------------------
    # Filtered views
    # ------------------------------------------------------------------

    def show_needs_confirmation(self) -> None:
        """Show records with research findings to confirm."""
        tasks = self.db.get_research_tasks(status=ResearchStatus.COMPLETED.value, limit=200)
        task_ids = {t.prospect_id for t in tasks}
        filtered = [p for p in self._prospects if p.id in task_ids]
        self._populate_tree(filtered)
        self._status_var.set(f"{len(filtered)} records with findings to confirm")

    def show_in_progress(self) -> None:
        """Show records currently being researched."""
        tasks = self.db.get_research_tasks(status=ResearchStatus.IN_PROGRESS.value, limit=200)
        task_ids = {t.prospect_id for t in tasks}
        filtered = [p for p in self._prospects if p.id in task_ids]
        self._populate_tree(filtered)
        self._status_var.set(f"{len(filtered)} records being researched")

    def show_manual_needed(self) -> None:
        """Show records needing manual research."""
        tasks = self.db.get_research_tasks(status=ResearchStatus.FAILED.value, limit=200)
        task_ids = {t.prospect_id for t in tasks}
        filtered = [p for p in self._prospects if p.id in task_ids]
        self._populate_tree(filtered)
        self._status_var.set(f"{len(filtered)} records need manual research")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _populate_tree(self, prospects: list[Prospect]) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)

        for p in prospects:
            company = self.db.get_company(p.company_id)
            company_name = company.name if company else ""
            notes_preview = (p.notes[:80] + "...") if p.notes and len(p.notes) > 80 else (p.notes or "")

            # Get research status
            tasks = self.db.get_research_tasks(status=None, limit=1)
            research_status = "Pending"
            for t in self.db.get_research_tasks(status=None, limit=500):
                if t.prospect_id == p.id:
                    research_status = t.status.value if hasattr(t.status, "value") else str(t.status)
                    break

            self._tree.insert(
                "", tk.END, iid=str(p.id),
                values=(p.full_name, company_name, research_status,
                        f"{p.data_confidence}%", notes_preview),
            )

        self._status_var.set(f"{len(prospects)} broken records")

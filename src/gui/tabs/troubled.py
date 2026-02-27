"""Troubled tab - Problem cards needing attention.

Displays overdue, stalled, and suspect-data prospects.
Data provided by TroubledCardsService.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.engine.troubled_cards import TroubledCardsService
from src.gui.tabs import TabBase
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)


class TroubledTab(TabBase):
    """Problem cards management.

    Shows three categories:
    - Overdue: follow-ups past due by 2+ days
    - Stalled: engaged with no activity in 14+ days
    - Suspect data: flagged contact methods
    """

    def __init__(self, parent: tk.Widget, db: Database):
        super().__init__(parent, db)
        self._cards: list = []
        self._tree: Optional[ttk.Treeview] = None
        self._header_label: Optional[tk.Label] = None
        self._create_ui()

    def _create_ui(self) -> None:
        """Build the troubled tab UI."""
        if not self.frame:
            return

        # Header
        self._header_label = tk.Label(
            self.frame,
            text="Troubled Cards",
            font=("Segoe UI", 14, "bold"),
            bg=COLORS["bg"],
            fg=COLORS["fg"],
        )
        self._header_label.pack(padx=12, pady=(8, 4), anchor="w")

        tk.Label(
            self.frame,
            text="Prospects that need attention \u2014 overdue, stalled, or suspect data",
            font=FONTS["small"],
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).pack(padx=12, pady=(0, 8), anchor="w")

        # Treeview
        tree_frame = ttk.Frame(self.frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        columns = ("ID", "Name", "Company", "Type", "Detail", "Days")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        self._tree.heading("ID", text="ID")
        self._tree.heading("Name", text="Name")
        self._tree.heading("Company", text="Company")
        self._tree.heading("Type", text="Problem")
        self._tree.heading("Detail", text="Detail")
        self._tree.heading("Days", text="Days")

        self._tree.column("ID", width=50)
        self._tree.column("Name", width=160)
        self._tree.column("Company", width=150)
        self._tree.column("Type", width=100)
        self._tree.column("Detail", width=220)
        self._tree.column("Days", width=60)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Color tags for trouble types
        self._tree.tag_configure("overdue", foreground=COLORS["danger"])
        self._tree.tag_configure("stalled", foreground=COLORS["warning"])
        self._tree.tag_configure("suspect_data", foreground="#e67e22")

    def refresh(self) -> None:
        """Reload troubled cards from database."""
        svc = TroubledCardsService(self.db)
        self._cards = svc.get_troubled_cards()

        # Update header
        if self._header_label:
            count = len(self._cards)
            overdue = sum(1 for c in self._cards if c.trouble_type == "overdue")
            stalled = sum(1 for c in self._cards if c.trouble_type == "stalled")
            suspect = sum(1 for c in self._cards if c.trouble_type == "suspect_data")
            self._header_label.config(
                text=f"Troubled Cards: {count} total \u2014 "
                f"{overdue} overdue, {stalled} stalled, {suspect} suspect data"
            )

        # Populate tree
        if self._tree:
            self._tree.delete(*self._tree.get_children())
            for card in self._cards:
                tag = card.trouble_type
                self._tree.insert(
                    "",
                    tk.END,
                    values=(
                        card.prospect_id,
                        card.prospect_name,
                        card.company_name or "",
                        card.trouble_type.replace("_", " ").title(),
                        card.detail,
                        card.days_overdue,
                    ),
                    tags=(tag,),
                )

        logger.debug(
            "Troubled tab refreshed",
            extra={"context": {"count": len(self._cards)}},
        )

    def on_activate(self) -> None:
        """Called when tab becomes visible."""
        self.refresh()

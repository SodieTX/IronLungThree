"""Prospect card display widget."""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from src.core.logging import get_logger
from src.db.models import Activity, Company, IntelNugget, Prospect
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)


class ProspectCard(tk.Frame):
    """Prospect card widget with glance, call, and deep dive views.

    Displays a single prospect's information in a card layout.
    Supports three view modes:
      - glance: compact overview (name, company, score, next action)
      - call:   call-focused view (phone numbers, script hints, timer)
      - deep:   full detail view (all fields, activities, intel)
    """

    def __init__(self, parent: tk.Widget):
        super().__init__(parent, bg=COLORS["bg_alt"], bd=1, relief=tk.RIDGE, padx=16, pady=12)
        self._prospect: Optional[Prospect] = None
        self._company: Optional[Company] = None
        self._activities: list[Activity] = []
        self._intel: list[IntelNugget] = []
        self._view_mode = "glance"

        # Build empty card layout
        self._content = tk.Frame(self, bg=COLORS["bg_alt"])
        self._content.pack(fill=tk.BOTH, expand=True)
        self._render()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_prospect(
        self,
        prospect: Prospect,
        company: Company,
        activities: list,
        intel: list,
    ) -> None:
        """Set prospect to display and refresh the card."""
        self._prospect = prospect
        self._company = company
        self._activities = activities
        self._intel = intel
        self._render()

    def set_view_mode(self, mode: str) -> None:
        """Set view mode: glance, call, or deep."""
        if mode not in ("glance", "call", "deep"):
            return
        self._view_mode = mode
        self._render()

    def enter_call_mode(self) -> None:
        """Enter call mode view."""
        self.set_view_mode("call")

    def exit_call_mode(self) -> None:
        """Exit call mode, return to glance."""
        self.set_view_mode("glance")

    def clear(self) -> None:
        """Clear the card display."""
        self._prospect = None
        self._company = None
        self._activities = []
        self._intel = []
        self._render()

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render(self) -> None:
        """Re-render the card content for the current view mode."""
        for child in self._content.winfo_children():
            child.destroy()

        if self._prospect is None:
            tk.Label(
                self._content,
                text="No prospect selected",
                font=FONTS["default"],
                bg=COLORS["bg_alt"],
                fg=COLORS["muted"],
            ).pack(pady=20)
            return

        if self._view_mode == "glance":
            self._render_glance()
        elif self._view_mode == "call":
            self._render_call()
        elif self._view_mode == "deep":
            self._render_deep()

    def _render_glance(self) -> None:
        """Compact overview."""
        p = self._prospect
        c = self._company
        assert p is not None

        # Name + score
        header = tk.Frame(self._content, bg=COLORS["bg_alt"])
        header.pack(fill=tk.X)
        tk.Label(
            header, text=p.full_name, font=("Segoe UI", 14, "bold"),
            bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor=tk.W,
        ).pack(side=tk.LEFT)
        tk.Label(
            header, text=f"Score: {p.prospect_score}", font=FONTS["mono"],
            bg=COLORS["bg_alt"], fg=COLORS["accent"],
        ).pack(side=tk.RIGHT)

        # Company + title
        company_name = c.name if c else "Unknown"
        title = p.title or ""
        subtitle = f"{title} @ {company_name}" if title else company_name
        tk.Label(
            self._content, text=subtitle, font=FONTS["default"],
            bg=COLORS["bg_alt"], fg=COLORS["muted"], anchor=tk.W,
        ).pack(fill=tk.X, pady=(2, 8))

        # Population + stage + follow-up
        info_row = tk.Frame(self._content, bg=COLORS["bg_alt"])
        info_row.pack(fill=tk.X)
        pop_text = p.population.value if p.population else "—"
        stage_text = f" / {p.engagement_stage.value}" if p.engagement_stage else ""
        tk.Label(
            info_row, text=f"Population: {pop_text}{stage_text}", font=FONTS["small"],
            bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor=tk.W,
        ).pack(side=tk.LEFT)

        if p.follow_up_date:
            tk.Label(
                info_row, text=f"Follow-up: {p.follow_up_date}", font=FONTS["small"],
                bg=COLORS["bg_alt"], fg=COLORS["fg"],
            ).pack(side=tk.RIGHT)

        # Notes preview
        if p.notes:
            ttk.Separator(self._content, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)
            preview = p.notes[:200] + ("..." if len(p.notes) > 200 else "")
            tk.Label(
                self._content, text=preview, font=FONTS["small"],
                bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor=tk.W,
                justify=tk.LEFT, wraplength=500,
            ).pack(fill=tk.X)

    def _render_call(self) -> None:
        """Call-focused view."""
        p = self._prospect
        c = self._company
        assert p is not None

        tk.Label(
            self._content, text=p.full_name, font=("Segoe UI", 16, "bold"),
            bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor=tk.W,
        ).pack(fill=tk.X)

        company_name = c.name if c else "Unknown"
        tk.Label(
            self._content, text=f"{p.title or ''} @ {company_name}",
            font=FONTS["large"], bg=COLORS["bg_alt"], fg=COLORS["muted"], anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 8))

        ttk.Separator(self._content, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)

        tk.Label(
            self._content, text=f"Attempts: {p.attempt_count}",
            font=FONTS["default"], bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor=tk.W,
        ).pack(fill=tk.X, pady=(4, 2))

        last_contact = str(p.last_contact_date) if p.last_contact_date else "Never"
        tk.Label(
            self._content, text=f"Last contact: {last_contact}",
            font=FONTS["default"], bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 4))

        if p.notes:
            ttk.Separator(self._content, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)
            tk.Label(
                self._content, text=p.notes[:300] + ("..." if len(p.notes) > 300 else ""),
                font=FONTS["small"], bg=COLORS["bg_alt"], fg=COLORS["fg"],
                anchor=tk.W, justify=tk.LEFT, wraplength=500,
            ).pack(fill=tk.X)

        tk.Label(
            self._content, text="CALL MODE", font=("Segoe UI", 9, "bold"),
            bg=COLORS["bg_alt"], fg=COLORS["accent"],
        ).pack(anchor=tk.E, pady=(8, 0))

    def _render_deep(self) -> None:
        """Full detail view with activities and intel."""
        p = self._prospect
        c = self._company
        assert p is not None

        tk.Label(
            self._content, text=p.full_name, font=("Segoe UI", 14, "bold"),
            bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor=tk.W,
        ).pack(fill=tk.X)

        company_name = c.name if c else "Unknown"
        tk.Label(
            self._content, text=f"{p.title or ''} @ {company_name}",
            font=FONTS["default"], bg=COLORS["bg_alt"], fg=COLORS["muted"], anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 6))

        # Details grid
        details = [
            ("Population", p.population.value if p.population else "—"),
            ("Stage", p.engagement_stage.value if p.engagement_stage else "—"),
            ("Score", str(p.prospect_score)),
            ("Confidence", f"{p.data_confidence}%"),
            ("Attempts", str(p.attempt_count)),
            ("Follow-up", str(p.follow_up_date) if p.follow_up_date else "—"),
            ("Last Contact", str(p.last_contact_date) if p.last_contact_date else "Never"),
            ("Source", p.source or "—"),
        ]
        ttk.Separator(self._content, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)
        for label_text, value in details:
            row = tk.Frame(self._content, bg=COLORS["bg_alt"])
            row.pack(fill=tk.X, pady=1)
            tk.Label(
                row, text=f"{label_text}:", font=("Segoe UI", 9, "bold"),
                bg=COLORS["bg_alt"], fg=COLORS["fg"], width=14, anchor=tk.W,
            ).pack(side=tk.LEFT)
            tk.Label(
                row, text=value, font=FONTS["small"],
                bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor=tk.W,
            ).pack(side=tk.LEFT)

        # Notes
        if p.notes:
            ttk.Separator(self._content, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)
            tk.Label(
                self._content, text="Notes:", font=("Segoe UI", 9, "bold"),
                bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor=tk.W,
            ).pack(fill=tk.X)
            tk.Label(
                self._content, text=p.notes, font=FONTS["small"],
                bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor=tk.W,
                justify=tk.LEFT, wraplength=500,
            ).pack(fill=tk.X)

        # Recent activities
        if self._activities:
            ttk.Separator(self._content, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)
            tk.Label(
                self._content, text=f"Recent Activity ({len(self._activities)})",
                font=("Segoe UI", 9, "bold"), bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor=tk.W,
            ).pack(fill=tk.X)
            for act in self._activities[:5]:
                outcome_str = f" ({act.outcome.value})" if act.outcome else ""
                tk.Label(
                    self._content,
                    text=f"  {act.created_at:%Y-%m-%d} {act.activity_type.value}{outcome_str}",
                    font=FONTS["small"], bg=COLORS["bg_alt"], fg=COLORS["muted"], anchor=tk.W,
                ).pack(fill=tk.X)

        # Intel nuggets
        if self._intel:
            ttk.Separator(self._content, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)
            tk.Label(
                self._content, text=f"Intel ({len(self._intel)})",
                font=("Segoe UI", 9, "bold"), bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor=tk.W,
            ).pack(fill=tk.X)
            for nugget in self._intel[:5]:
                tk.Label(
                    self._content,
                    text=f"  [{nugget.category.value}] {nugget.content}",
                    font=FONTS["small"], bg=COLORS["bg_alt"], fg=COLORS["muted"], anchor=tk.W,
                ).pack(fill=tk.X)

"""Prospect card display widget.

Three interaction modes:
    - Glance: Default processing view. Name, company, phone, why up today,
      last interaction, scores.
    - Call: During phone calls. Large name/company, last 3 interactions,
      intel nuggets as cheat sheet.
    - Deep: Full history, all contact methods, company context, all notes.
"""

import tkinter as tk
from datetime import date
from tkinter import ttk
from typing import Optional

from src.core.logging import get_logger
from src.db.models import (
    Activity,
    Company,
    ContactMethod,
    IntelNugget,
    Population,
    Prospect,
)
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)


class ProspectCard(tk.Frame):
    """Prospect card widget with glance, call, and deep dive views."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent, bg=COLORS["bg_alt"], bd=1, relief="solid")
        self._prospect: Optional[Prospect] = None
        self._company: Optional[Company] = None
        self._activities: list[Activity] = []
        self._intel: list[IntelNugget] = []
        self._contact_methods: list[ContactMethod] = []
        self._company_contacts: int = 0
        self._view_mode = "glance"
        self._widgets: list[tk.Widget] = []

    def set_prospect(
        self,
        prospect: Prospect,
        company: Company,
        activities: list,
        intel: list,
        contact_methods: Optional[list] = None,
        company_contacts: int = 0,
    ) -> None:
        """Set prospect to display and rebuild the card."""
        self._prospect = prospect
        self._company = company
        self._activities = activities or []
        self._intel = intel or []
        self._contact_methods = contact_methods or []
        self._company_contacts = company_contacts
        self._rebuild()

    def set_view_mode(self, mode: str) -> None:
        """Set view mode: glance, call, or deep."""
        if mode not in ("glance", "call", "deep"):
            logger.warning(f"Invalid view mode: {mode}")
            return
        self._view_mode = mode
        self._rebuild()

    def enter_call_mode(self) -> None:
        """Enter call mode view."""
        self.set_view_mode("call")

    def exit_call_mode(self) -> None:
        """Exit call mode, return to glance."""
        self.set_view_mode("glance")

    def _rebuild(self) -> None:
        """Clear and rebuild the card contents for current mode."""
        for w in self._widgets:
            w.destroy()
        self._widgets.clear()

        if self._prospect is None:
            return

        if self._view_mode == "glance":
            self._build_glance()
        elif self._view_mode == "call":
            self._build_call()
        elif self._view_mode == "deep":
            self._build_deep()

    # ------------------------------------------------------------------
    # GLANCE VIEW
    # ------------------------------------------------------------------

    def _build_glance(self) -> None:
        """Build glance view — the default processing view."""
        p = self._prospect
        c = self._company
        if p is None:
            return

        # Name + title
        name_text = p.full_name
        if p.title:
            name_text += f", {p.title}"
        name_lbl = tk.Label(
            self, text=name_text, font=("Segoe UI", 14, "bold"),
            bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor="w",
        )
        name_lbl.pack(fill=tk.X, padx=12, pady=(10, 0))
        self._widgets.append(name_lbl)

        # Company line
        company_text = c.name if c else "No company"
        if c and c.loan_types:
            company_text += f" ({c.loan_types})"
        comp_lbl = tk.Label(
            self, text=company_text, font=FONTS["default"],
            bg=COLORS["bg_alt"], fg=COLORS["muted"], anchor="w",
        )
        comp_lbl.pack(fill=tk.X, padx=12, pady=2)
        self._widgets.append(comp_lbl)

        # Phone number
        phone = self._get_primary_phone()
        if phone:
            phone_lbl = tk.Label(
                self, text=f"Phone: {phone}", font=FONTS["default"],
                bg=COLORS["bg_alt"], fg=COLORS["accent"], anchor="w", cursor="hand2",
            )
            phone_lbl.pack(fill=tk.X, padx=12, pady=2)
            self._widgets.append(phone_lbl)

        # Separator
        sep = ttk.Separator(self, orient="horizontal")
        sep.pack(fill=tk.X, padx=12, pady=6)
        self._widgets.append(sep)

        # Why up today
        why_text = self._get_why_up_today()
        why_lbl = tk.Label(
            self, text=why_text, font=("Segoe UI", 10, "italic"),
            bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor="w", wraplength=450,
        )
        why_lbl.pack(fill=tk.X, padx=12, pady=2)
        self._widgets.append(why_lbl)

        # Last interaction
        last = self._get_last_interaction()
        if last:
            last_lbl = tk.Label(
                self, text=last, font=FONTS["small"],
                bg=COLORS["bg_alt"], fg=COLORS["muted"], anchor="w", wraplength=450,
            )
            last_lbl.pack(fill=tk.X, padx=12, pady=2)
            self._widgets.append(last_lbl)

        # Scores row
        score_frame = tk.Frame(self, bg=COLORS["bg_alt"])
        score_frame.pack(fill=tk.X, padx=12, pady=(6, 4))
        self._widgets.append(score_frame)

        score_val = p.prospect_score or 0
        conf_val = p.data_confidence or 0
        self._add_badge(score_frame, f"Score: {score_val}", self._score_color(score_val))
        self._add_badge(score_frame, f"Confidence: {conf_val}", self._score_color(conf_val))

        if p.population:
            pop_color = self._population_color(p.population)
            self._add_badge(score_frame, p.population.value, pop_color)

        # Company context
        if self._company_contacts > 0:
            company_name = c.name if c else "this company"
            ctx_lbl = tk.Label(
                self,
                text=f"{self._company_contacts} other contact(s) at {company_name}",
                font=FONTS["small"], bg=COLORS["bg_alt"], fg=COLORS["warning"],
                anchor="w",
            )
            ctx_lbl.pack(fill=tk.X, padx=12, pady=(0, 8))
            self._widgets.append(ctx_lbl)

    # ------------------------------------------------------------------
    # CALL VIEW
    # ------------------------------------------------------------------

    def _build_call(self) -> None:
        """Build call mode — cheat sheet during phone calls."""
        p = self._prospect
        c = self._company
        if p is None:
            return

        # Large name for glancing while talking
        name_lbl = tk.Label(
            self, text=p.full_name, font=("Segoe UI", 20, "bold"),
            bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor="w",
        )
        name_lbl.pack(fill=tk.X, padx=12, pady=(12, 0))
        self._widgets.append(name_lbl)

        title_text = p.title or ""
        if c:
            title_text += f" @ {c.name}" if title_text else c.name
        if title_text:
            title_lbl = tk.Label(
                self, text=title_text, font=("Segoe UI", 14),
                bg=COLORS["bg_alt"], fg=COLORS["muted"], anchor="w",
            )
            title_lbl.pack(fill=tk.X, padx=12, pady=(0, 4))
            self._widgets.append(title_lbl)

        sep = ttk.Separator(self, orient="horizontal")
        sep.pack(fill=tk.X, padx=12, pady=6)
        self._widgets.append(sep)

        # Last 3 interactions
        recent = self._activities[:3]
        if recent:
            hdr = tk.Label(
                self, text="RECENT INTERACTIONS", font=("Segoe UI", 9, "bold"),
                bg=COLORS["bg_alt"], fg=COLORS["muted"], anchor="w",
            )
            hdr.pack(fill=tk.X, padx=12, pady=(4, 2))
            self._widgets.append(hdr)

            for act in recent:
                line = self._format_activity_brief(act)
                act_lbl = tk.Label(
                    self, text=line, font=FONTS["small"],
                    bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor="w",
                    wraplength=450,
                )
                act_lbl.pack(fill=tk.X, padx=20, pady=1)
                self._widgets.append(act_lbl)

        # Intel nuggets
        if self._intel:
            sep2 = ttk.Separator(self, orient="horizontal")
            sep2.pack(fill=tk.X, padx=12, pady=6)
            self._widgets.append(sep2)

            intel_hdr = tk.Label(
                self, text="INTEL", font=("Segoe UI", 9, "bold"),
                bg=COLORS["bg_alt"], fg=COLORS["muted"], anchor="w",
            )
            intel_hdr.pack(fill=tk.X, padx=12, pady=(4, 2))
            self._widgets.append(intel_hdr)

            for nugget in self._intel[:5]:
                cat = nugget.category.value if nugget.category else ""
                nugget_lbl = tk.Label(
                    self, text=f"  {cat}: {nugget.content}",
                    font=FONTS["small"], bg=COLORS["bg_alt"], fg=COLORS["fg"],
                    anchor="w", wraplength=450,
                )
                nugget_lbl.pack(fill=tk.X, padx=12, pady=1)
                self._widgets.append(nugget_lbl)

    # ------------------------------------------------------------------
    # DEEP DIVE VIEW
    # ------------------------------------------------------------------

    def _build_deep(self) -> None:
        """Build deep dive view — full history and details."""
        p = self._prospect
        c = self._company
        if p is None:
            return

        # Scrollable container
        canvas = tk.Canvas(self, bg=COLORS["bg_alt"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=COLORS["bg_alt"])

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._widgets.extend([canvas, scrollbar])

        # --- Identity ---
        self._deep_section(scroll_frame, "PROSPECT")
        self._deep_field(scroll_frame, "Name", p.full_name)
        self._deep_field(scroll_frame, "Title", p.title)
        self._deep_field(scroll_frame, "Population", p.population.value if p.population else "")
        if p.engagement_stage:
            self._deep_field(scroll_frame, "Stage", p.engagement_stage.value)
        self._deep_field(scroll_frame, "Score", str(p.prospect_score or 0))
        self._deep_field(scroll_frame, "Confidence", str(p.data_confidence or 0))
        self._deep_field(scroll_frame, "Attempts", str(p.attempt_count or 0))
        if p.follow_up_date:
            self._deep_field(scroll_frame, "Follow-up", str(p.follow_up_date)[:10])
        if p.source:
            self._deep_field(scroll_frame, "Source", p.source)

        # --- Company ---
        if c:
            self._deep_section(scroll_frame, "COMPANY")
            self._deep_field(scroll_frame, "Company", c.name)
            self._deep_field(scroll_frame, "Domain", c.domain)
            self._deep_field(scroll_frame, "Loan Types", c.loan_types)
            self._deep_field(scroll_frame, "Size", c.size)
            self._deep_field(scroll_frame, "State", c.state)
            self._deep_field(scroll_frame, "Timezone", c.timezone)

            if self._company_contacts > 0:
                tk.Label(
                    scroll_frame,
                    text=f"  {self._company_contacts} other contact(s) at this company",
                    font=FONTS["small"], bg=COLORS["bg_alt"], fg=COLORS["warning"],
                    anchor="w",
                ).pack(fill=tk.X, padx=12, pady=2)

        # --- Contact Methods ---
        if self._contact_methods:
            self._deep_section(scroll_frame, "CONTACT METHODS")
            for cm in self._contact_methods:
                verified = " [verified]" if cm.is_verified else ""
                suspect = " [SUSPECT]" if cm.is_suspect else ""
                primary = " (primary)" if cm.is_primary else ""
                label = cm.label or (cm.type.value if cm.type else "")
                line = f"  {label}: {cm.value}{primary}{verified}{suspect}"
                tk.Label(
                    scroll_frame, text=line, font=FONTS["small"],
                    bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor="w",
                ).pack(fill=tk.X, padx=12, pady=2)

        # --- Notes ---
        if p.notes:
            self._deep_section(scroll_frame, "NOTES")
            tk.Label(
                scroll_frame, text=p.notes, font=FONTS["small"],
                bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor="w",
                wraplength=450, justify="left",
            ).pack(fill=tk.X, padx=12, pady=2)

        # --- Intel Nuggets ---
        if self._intel:
            self._deep_section(scroll_frame, "INTEL")
            for nugget in self._intel:
                cat = nugget.category.value if nugget.category else ""
                tk.Label(
                    scroll_frame, text=f"  {cat}: {nugget.content}",
                    font=FONTS["small"], bg=COLORS["bg_alt"], fg=COLORS["fg"],
                    anchor="w", wraplength=450,
                ).pack(fill=tk.X, padx=12, pady=2)

        # --- Activity History ---
        self._deep_section(scroll_frame, f"ACTIVITY HISTORY ({len(self._activities)})")
        for act in self._activities:
            line = self._format_activity_full(act)
            tk.Label(
                scroll_frame, text=line, font=FONTS["small"],
                bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor="w",
                wraplength=450, justify="left",
            ).pack(fill=tk.X, padx=20, pady=1)

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _deep_section(self, parent: tk.Widget, title: str) -> None:
        """Add a section header in deep view."""
        ttk.Separator(parent, orient="horizontal").pack(fill=tk.X, padx=12, pady=(8, 2))
        tk.Label(
            parent, text=title, font=("Segoe UI", 10, "bold"),
            bg=COLORS["bg_alt"], fg=COLORS["accent"], anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(2, 4))

    def _deep_field(self, parent: tk.Widget, label: str, value: Optional[str]) -> None:
        """Add a labeled field in deep view."""
        if not value:
            return
        row = tk.Frame(parent, bg=COLORS["bg_alt"])
        row.pack(fill=tk.X, padx=20, pady=1)
        tk.Label(
            row, text=f"{label}:", font=("Segoe UI", 9, "bold"),
            bg=COLORS["bg_alt"], fg=COLORS["muted"], width=14, anchor="e",
        ).pack(side=tk.LEFT)
        tk.Label(
            row, text=value, font=FONTS["small"],
            bg=COLORS["bg_alt"], fg=COLORS["fg"], anchor="w",
        ).pack(side=tk.LEFT, padx=(4, 0))

    def _add_badge(self, parent: tk.Frame, text: str, color: str) -> None:
        """Add a small colored badge."""
        tk.Label(
            parent, text=f" {text} ", font=FONTS["small"],
            bg=color, fg="#ffffff", relief="flat",
        ).pack(side=tk.LEFT, padx=(0, 6))

    def _get_primary_phone(self) -> Optional[str]:
        """Get the primary phone number."""
        for cm in self._contact_methods:
            if cm.type and cm.type.value == "phone" and cm.is_primary:
                return cm.value
        for cm in self._contact_methods:
            if cm.type and cm.type.value == "phone":
                return cm.value
        return None

    def _get_why_up_today(self) -> str:
        """Generate the 'why this card is up today' text."""
        p = self._prospect
        if p is None:
            return ""

        if p.population == Population.ENGAGED:
            if p.follow_up_date:
                fu_str = str(p.follow_up_date)[:10]
                try:
                    fu_date = date.fromisoformat(fu_str)
                    days_overdue = (date.today() - fu_date).days
                    if days_overdue > 0:
                        return f"Follow-up overdue by {days_overdue} day(s)"
                    elif days_overdue == 0:
                        return "Follow-up scheduled for today"
                    else:
                        return f"Follow-up in {-days_overdue} day(s)"
                except (ValueError, TypeError):
                    return "Engaged — follow-up scheduled"
            return "Engaged — no follow-up date set (orphan)"

        if p.population == Population.UNENGAGED:
            attempt = (p.attempt_count or 0) + 1
            return f"Attempt #{attempt} — unengaged outreach"

        if p.population == Population.BROKEN:
            return "Broken — missing contact data"

        return f"Population: {p.population.value}" if p.population else ""

    def _get_last_interaction(self) -> Optional[str]:
        """Get a one-line summary of the last interaction."""
        if not self._activities:
            return None
        return self._format_activity_brief(self._activities[0])

    def _format_activity_brief(self, act: Activity) -> str:
        """Format an activity as a brief one-liner."""
        date_str = ""
        if act.created_at:
            try:
                if isinstance(act.created_at, str):
                    date_str = act.created_at[:10]
                else:
                    date_str = act.created_at.strftime("%m/%d")
            except (ValueError, AttributeError):
                date_str = ""

        atype = act.activity_type.value if act.activity_type else "note"
        outcome = f" ({act.outcome.value})" if act.outcome else ""
        notes_snippet = ""
        if act.notes:
            snippet = act.notes[:80]
            if len(act.notes) > 80:
                snippet += "..."
            notes_snippet = f" — {snippet}"

        return f"{date_str}: {atype}{outcome}{notes_snippet}"

    def _format_activity_full(self, act: Activity) -> str:
        """Format an activity with full detail."""
        date_str = ""
        if act.created_at:
            try:
                if isinstance(act.created_at, str):
                    date_str = act.created_at[:16]
                else:
                    date_str = act.created_at.strftime("%Y-%m-%d %H:%M")
            except (ValueError, AttributeError):
                date_str = ""

        atype = act.activity_type.value if act.activity_type else "note"
        outcome = f" | {act.outcome.value}" if act.outcome else ""
        by = f" [{act.created_by}]" if act.created_by else ""
        notes = f"\n    {act.notes}" if act.notes else ""

        return f"{date_str} | {atype}{outcome}{by}{notes}"

    def _score_color(self, score: int) -> str:
        """Get color for a score value."""
        if score >= 70:
            return COLORS["success"]
        if score >= 40:
            return COLORS["warning"]
        return COLORS["danger"]

    def _population_color(self, pop: Population) -> str:
        """Get color for a population."""
        mapping = {
            Population.ENGAGED: COLORS["success"],
            Population.UNENGAGED: COLORS["accent"],
            Population.BROKEN: COLORS["danger"],
            Population.PARKED: COLORS["muted"],
            Population.DEAD_DNC: "#333333",
            Population.LOST: COLORS["danger"],
            Population.CLOSED_WON: COLORS["success"],
            Population.PARTNERSHIP: COLORS["accent"],
        }
        return mapping.get(pop, COLORS["muted"])

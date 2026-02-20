"""Demos tab - Demo invite creation and tracking.

Displays upcoming and completed demos, provides demo invite creation,
and generates demo prep documents.
"""

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, ttk
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityOutcome,
    ActivityType,
    EngagementStage,
    Population,
    Prospect,
)
from src.gui.tabs import TabBase
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)

# Demo duration options in minutes
DURATION_OPTIONS = [15, 30, 45, 60]


class DemosTab(TabBase):
    """Demo management tab with invite creator and tracking."""

    def __init__(self, parent: tk.Widget, db: Database):
        super().__init__(parent, db)
        self._tree: Optional[ttk.Treeview] = None
        self._view_mode = "upcoming"  # "upcoming" or "completed"
        self._prep_text: Optional[tk.Text] = None
        self._create_ui()

    def _create_ui(self) -> None:
        """Build the demos tab UI."""
        if not self.frame:
            return

        # Top bar with action buttons
        top = ttk.Frame(self.frame)
        top.pack(fill=tk.X, padx=8, pady=8)

        tk.Label(
            top,
            text="Demos",
            font=FONTS["large"],
            bg=COLORS["bg"],
            fg=COLORS["fg"],
        ).pack(side=tk.LEFT, padx=8)

        ttk.Button(top, text="Create Invite", command=self.create_invite).pack(side=tk.LEFT, padx=8)

        # Toggle between upcoming and completed
        ttk.Button(top, text="Upcoming", command=self.show_upcoming).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="Completed", command=self.show_completed).pack(side=tk.RIGHT, padx=4)

        # Main content: split pane — demo list left, prep right
        paned = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # Left: demo list
        left = ttk.Frame(paned)
        paned.add(left, weight=2)

        self._tree = ttk.Treeview(
            left,
            columns=("ID", "Name", "Company", "Date", "Status"),
            show="headings",
            selectmode="browse",
        )
        self._tree.heading("ID", text="ID")
        self._tree.heading("Name", text="Name")
        self._tree.heading("Company", text="Company")
        self._tree.heading("Date", text="Date")
        self._tree.heading("Status", text="Status")
        self._tree.column("ID", width=40)
        self._tree.column("Name", width=150)
        self._tree.column("Company", width=150)
        self._tree.column("Date", width=120)
        self._tree.column("Status", width=100)

        scrollbar = ttk.Scrollbar(left, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._tree.bind("<Double-Button-1>", self._on_demo_select)

        # Right: demo prep display
        right = ttk.Frame(paned)
        paned.add(right, weight=1)

        tk.Label(
            right,
            text="DEMO PREP",
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["bg"],
            fg=COLORS["accent"],
        ).pack(anchor="w", padx=8, pady=(8, 4))

        self._prep_text = tk.Text(
            right,
            wrap=tk.WORD,
            font=FONTS["small"],
            bg=COLORS["bg_alt"],
            fg=COLORS["fg"],
            padx=12,
            pady=8,
            relief="flat",
        )
        self._prep_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self._prep_text.insert("1.0", "Select a demo to see prep details.")
        self._prep_text.config(state="disabled")

        # Bottom bar: mark complete button
        bottom = ttk.Frame(self.frame)
        bottom.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Button(bottom, text="Mark Demo Complete", command=self._mark_complete).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(bottom, text="Generate Prep", command=self._generate_prep).pack(
            side=tk.LEFT, padx=4
        )

    def refresh(self) -> None:
        """Reload demo data from database."""
        if self._view_mode == "upcoming":
            self.show_upcoming()
        else:
            self.show_completed()

    def on_activate(self) -> None:
        """Called when this tab becomes visible."""
        self.refresh()

    def create_invite(self) -> None:
        """Open demo invite creator dialog."""
        if not self.frame:
            return

        dialog = DemoInviteDialog(self.frame, self.db)
        if dialog.show():
            self.refresh()

    def show_upcoming(self) -> None:
        """Show upcoming demos."""
        self._view_mode = "upcoming"
        self._load_demos(completed=False)

    def show_completed(self) -> None:
        """Show completed demos."""
        self._view_mode = "completed"
        self._load_demos(completed=True)

    def _load_demos(self, completed: bool = False) -> None:
        """Load demos into the treeview."""
        if not self._tree:
            return

        self._tree.delete(*self._tree.get_children())

        if completed:
            # Show prospects with demo_completed activities
            prospects = self.db.get_prospects(population=Population.ENGAGED)
            prospects += self.db.get_prospects(population=Population.CLOSED_WON)
            demo_prospects: list[tuple[Prospect, str]] = []
            for p in prospects:
                activities = self.db.get_activities(p.id, limit=50) if p.id else []
                has_completed = any(
                    a.activity_type == ActivityType.DEMO_COMPLETED for a in activities
                )
                if has_completed:
                    demo_prospects.append((p, "completed"))
        else:
            # Show prospects with DEMO_SCHEDULED engagement stage
            prospects = self.db.get_prospects(population=Population.ENGAGED)
            demo_prospects = []
            for p in prospects:
                if p.engagement_stage == EngagementStage.DEMO_SCHEDULED:
                    demo_prospects.append((p, "scheduled"))
                elif p.engagement_stage == EngagementStage.PRE_DEMO:
                    demo_prospects.append((p, "pre_demo"))

        for prospect, status in demo_prospects:
            company = self.db.get_company(prospect.company_id) if prospect.company_id else None
            company_name = company.name if company else ""
            fu_date = ""
            if prospect.follow_up_date:
                try:
                    if isinstance(prospect.follow_up_date, str):
                        fu_date = prospect.follow_up_date[:10]
                    else:
                        fu_date = prospect.follow_up_date.strftime("%Y-%m-%d %H:%M")
                except (ValueError, AttributeError):
                    fu_date = str(prospect.follow_up_date)[:10]

            self._tree.insert(
                "",
                tk.END,
                values=(
                    prospect.id,
                    prospect.full_name,
                    company_name,
                    fu_date,
                    status,
                ),
            )

    def _on_demo_select(self, event: object) -> None:
        """Handle double-click on a demo row to show prep."""
        self._generate_prep()

    def _generate_prep(self) -> None:
        """Generate and display demo prep for selected prospect."""
        if not self._tree or not self._prep_text:
            return

        selection = self._tree.selection()
        if not selection:
            if self.frame:
                messagebox.showinfo(
                    "No Selection",
                    "Select a demo first.",
                    parent=self.frame.winfo_toplevel(),
                )
            return

        item = self._tree.item(selection[0])
        prospect_id = int(item["values"][0])

        try:
            from src.engine.demo_prep import generate_prep

            prep = generate_prep(self.db, prospect_id)

            # Format the prep document
            lines = [
                f"DEMO PREP: {prep.prospect_name}",
                f"Company: {prep.company_name}",
                "",
            ]

            if prep.loan_types:
                lines.append(f"Loan Types: {', '.join(prep.loan_types)}")
            if prep.company_size:
                lines.append(f"Company Size: {prep.company_size}")
            if prep.state:
                lines.append(f"State: {prep.state}")

            if prep.pain_points:
                lines.append("")
                lines.append("PAIN POINTS:")
                for pp in prep.pain_points:
                    lines.append(f"  - {pp}")

            if prep.competitors:
                lines.append("")
                lines.append("COMPETITORS:")
                for comp in prep.competitors:
                    lines.append(f"  - {comp}")

            if prep.decision_timeline:
                lines.append("")
                lines.append(f"TIMELINE: {prep.decision_timeline}")

            if prep.talking_points:
                lines.append("")
                lines.append("TALKING POINTS:")
                for tp in prep.talking_points:
                    lines.append(f"  - {tp}")

            if prep.questions_to_ask:
                lines.append("")
                lines.append("QUESTIONS TO ASK:")
                for q in prep.questions_to_ask:
                    lines.append(f"  - {q}")

            if prep.history_summary:
                lines.append("")
                lines.append(f"HISTORY: {prep.history_summary}")

            self._prep_text.config(state="normal")
            self._prep_text.delete("1.0", tk.END)
            self._prep_text.insert("1.0", "\n".join(lines))
            self._prep_text.config(state="disabled")

        except Exception as e:
            logger.error(f"Failed to generate demo prep: {e}")
            self._prep_text.config(state="normal")
            self._prep_text.delete("1.0", tk.END)
            self._prep_text.insert("1.0", f"Error generating prep: {e}")
            self._prep_text.config(state="disabled")

    def _mark_complete(self) -> None:
        """Mark selected demo as completed."""
        if not self._tree:
            return

        selection = self._tree.selection()
        if not selection:
            if self.frame:
                messagebox.showinfo(
                    "No Selection",
                    "Select a demo first.",
                    parent=self.frame.winfo_toplevel(),
                )
            return

        item = self._tree.item(selection[0])
        prospect_id = int(item["values"][0])

        # Log demo completed activity
        activity = Activity(
            prospect_id=prospect_id,
            activity_type=ActivityType.DEMO_COMPLETED,
            outcome=ActivityOutcome.DEMO_COMPLETED,
            notes="Demo completed",
            created_by="user",
        )
        self.db.create_activity(activity)

        # Update engagement stage to POST_DEMO
        prospect = self.db.get_prospect(prospect_id)
        if prospect:
            prospect.engagement_stage = EngagementStage.POST_DEMO
            self.db.update_prospect(prospect)

        logger.info(f"Demo marked complete for prospect {prospect_id}")
        self.refresh()


class DemoInviteDialog:
    """Demo invite creator dialog."""

    def __init__(self, parent: tk.Widget, db: Database):
        self.parent = parent
        self.db = db
        self._dialog: Optional[tk.Toplevel] = None
        self._prospect_var = tk.StringVar()
        self._duration_var = tk.StringVar(value="30")
        self._date_var = tk.StringVar()
        self._time_var = tk.StringVar(value="14:00")
        self._teams_var = tk.BooleanVar(value=True)
        self._created = False
        self._prospects: list[Prospect] = []

    def show(self) -> bool:
        """Display the demo invite dialog. Returns True if invite created."""
        self._dialog = tk.Toplevel(self.parent)
        self._dialog.title("Create Demo Invite")
        self._dialog.geometry("480x420")
        self._dialog.transient(self.parent.winfo_toplevel())
        self._dialog.grab_set()

        main = ttk.Frame(self._dialog, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        # Prospect selector
        ttk.Label(main, text="Prospect:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 4)
        )
        # Load engaged prospects
        self._prospects = self.db.get_prospects(population=Population.ENGAGED)
        prospect_names = [f"{p.id}: {p.full_name}" for p in self._prospects]

        ttk.Combobox(
            main,
            textvariable=self._prospect_var,
            values=prospect_names,
            state="readonly",
            width=40,
        ).pack(fill=tk.X, padx=4, pady=(0, 8))

        # Date
        ttk.Label(main, text="Date (YYYY-MM-DD):", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 4)
        )
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        self._date_var.set(tomorrow)
        ttk.Entry(main, textvariable=self._date_var, width=20).pack(anchor="w", padx=4, pady=(0, 8))

        # Time
        ttk.Label(main, text="Time (HH:MM):", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 4)
        )
        ttk.Entry(main, textvariable=self._time_var, width=10).pack(anchor="w", padx=4, pady=(0, 8))

        # Duration
        ttk.Label(main, text="Duration:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 4)
        )
        dur_frame = ttk.Frame(main)
        dur_frame.pack(fill=tk.X, padx=4, pady=(0, 8))
        for minutes in DURATION_OPTIONS:
            ttk.Radiobutton(
                dur_frame,
                text=f"{minutes} min",
                variable=self._duration_var,
                value=str(minutes),
            ).pack(side=tk.LEFT, padx=4)

        # Teams meeting checkbox
        ttk.Checkbutton(
            main,
            text="Include Teams meeting link",
            variable=self._teams_var,
        ).pack(anchor="w", padx=4, pady=(0, 12))

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(pady=8)
        ttk.Button(btn_frame, text="Create Invite", command=self._on_create).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side=tk.LEFT, padx=8)

        self._dialog.wait_window()
        return self._created

    def _on_create(self) -> None:
        """Create the demo invite."""
        prospect_sel = self._prospect_var.get()
        if not prospect_sel:
            parent = self._dialog if self._dialog else self.parent.winfo_toplevel()
            messagebox.showwarning("Missing", "Select a prospect.", parent=parent)
            return

        # Parse prospect ID from "ID: Name" format
        try:
            prospect_id = int(prospect_sel.split(":")[0].strip())
        except (ValueError, IndexError):
            return

        # Parse date and time
        date_str = self._date_var.get().strip()
        time_str = self._time_var.get().strip()
        try:
            demo_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            parent = self._dialog if self._dialog else self.parent.winfo_toplevel()
            messagebox.showwarning(
                "Invalid Date/Time",
                "Use YYYY-MM-DD for date and HH:MM for time.",
                parent=parent,
            )
            return

        duration = int(self._duration_var.get())

        # Update prospect: set engagement stage and follow-up date
        prospect = self.db.get_prospect(prospect_id)
        if prospect:
            prospect.engagement_stage = EngagementStage.DEMO_SCHEDULED
            prospect.follow_up_date = demo_dt
            self.db.update_prospect(prospect)

        # Log demo scheduled activity
        notes = f"Demo scheduled: {date_str} {time_str} ({duration} min)"
        if self._teams_var.get():
            notes += " | Teams meeting"

        activity = Activity(
            prospect_id=prospect_id,
            activity_type=ActivityType.DEMO_SCHEDULED,
            outcome=ActivityOutcome.DEMO_SET,
            notes=notes,
            created_by="user",
        )
        self.db.create_activity(activity)

        logger.info(
            f"Demo invite created for prospect {prospect_id}",
            extra={
                "context": {
                    "prospect_id": prospect_id,
                    "date": date_str,
                    "duration": duration,
                }
            },
        )

        self._created = True
        if self._dialog:
            self._dialog.destroy()

    def _on_cancel(self) -> None:
        """Cancel dialog."""
        if self._dialog:
            self._dialog.destroy()

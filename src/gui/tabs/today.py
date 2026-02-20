"""Today tab - Morning brief and card processing.

Primary work surface. Queue loads at morning brief start.
Cards display one at a time. User disposes each card, then next.
"""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    Company,
    Prospect,
)
from src.engine.cadence import get_todays_queue
from src.gui.adhd.audio import AudioManager, Sound
from src.gui.adhd.dopamine import DopamineEngine, WinType
from src.gui.cards import ProspectCard
from src.gui.dialogs.morning_brief import MorningBriefDialog
from src.gui.dialogs.quick_action import QuickActionDialog
from src.gui.tabs import TabBase
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)


class TodayTab(TabBase):
    """Today tab with queue processing."""

    def __init__(self, parent: tk.Widget, db: Database):
        super().__init__(parent, db)
        self._queue: list[Prospect] = []
        self._queue_index: int = 0
        self._card: Optional[ProspectCard] = None
        self._card_frame: Optional[tk.Frame] = None
        self._status_label: Optional[tk.Label] = None
        self._queue_label: Optional[tk.Label] = None
        self._action_frame: Optional[tk.Frame] = None
        self._notes_text: Optional[tk.Text] = None
        self._search_var = tk.StringVar()
        self._brief_shown = False
        self._audio = AudioManager()
        self._dopamine = DopamineEngine()
        self._create_ui()

    def _create_ui(self) -> None:
        """Create the Today tab UI."""
        if not self.frame:
            return

        # Top bar: queue info + search + brief button
        top = ttk.Frame(self.frame)
        top.pack(fill=tk.X, padx=8, pady=8)

        self._queue_label = tk.Label(
            top,
            text="Queue: 0 cards",
            font=FONTS["large"],
            bg=COLORS["bg"],
            fg=COLORS["fg"],
        )
        self._queue_label.pack(side=tk.LEFT, padx=8)

        # Quick search (Step 2.12)
        ttk.Label(top, text="Search:").pack(side=tk.LEFT, padx=(16, 4))
        search_entry = ttk.Entry(top, textvariable=self._search_var, width=24)
        search_entry.pack(side=tk.LEFT)
        search_entry.bind("<Return>", lambda e: self._quick_search())
        ttk.Button(top, text="Find", command=self._quick_search).pack(side=tk.LEFT, padx=4)

        # Re-read brief button
        ttk.Button(top, text="Today's Brief", command=self.show_morning_brief).pack(
            side=tk.RIGHT, padx=8
        )

        # Main content: card in center
        self._card_frame = tk.Frame(self.frame, bg=COLORS["bg"])
        self._card_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        # Empty state message
        self._status_label = tk.Label(
            self._card_frame,
            text="No cards queued.\nClick 'Today's Brief' to load today's queue.",
            font=FONTS["large"],
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        )
        self._status_label.pack(expand=True)

        # Bottom action bar
        self._action_frame = tk.Frame(self.frame, bg=COLORS["bg"])
        self._action_frame.pack(fill=tk.X, padx=16, pady=(0, 8))

        # Notes input
        notes_row = ttk.Frame(self._action_frame)
        notes_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(notes_row, text="Notes:").pack(side=tk.LEFT, padx=(0, 4))
        self._notes_text = tk.Text(notes_row, height=2, width=60, font=FONTS["small"])
        self._notes_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Action buttons
        btn_row = ttk.Frame(self._action_frame)
        btn_row.pack(fill=tk.X)

        ttk.Button(btn_row, text="Quick Action", command=self._quick_action).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(btn_row, text="Deep Dive", command=self._toggle_deep).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="Edit", command=self._edit_prospect).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="Skip", command=self._skip_card).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="Next", command=self.next_card).pack(side=tk.RIGHT, padx=4)

    def refresh(self) -> None:
        """Reload queue from database."""
        self._queue = get_todays_queue(self.db)
        self._queue_index = 0
        self._update_queue_label()
        self._show_current_card()

    def on_activate(self) -> None:
        """Called when this tab becomes visible."""
        if not self._brief_shown:
            self._brief_shown = True
            self.refresh()
            self.show_morning_brief()
        else:
            self._update_queue_label()

    def show_morning_brief(self) -> None:
        """Display morning brief dialog."""
        if not self.frame:
            return

        try:
            from src.content.morning_brief import generate_morning_brief

            brief = generate_morning_brief(self.db)
            dialog = MorningBriefDialog(self.frame, brief.full_text, on_ready=self.start_processing)
            dialog.show()
        except Exception as e:
            logger.error(f"Failed to generate morning brief: {e}")
            self.start_processing()

    def start_processing(self) -> None:
        """Start card processing loop."""
        # Get current energy level for queue ordering
        energy = self._get_energy_level()
        self._queue = get_todays_queue(self.db, energy=energy)
        self._queue_index = 0
        self._update_queue_label()
        self._show_current_card()
        energy_note = f" (energy: {energy})" if energy else ""
        logger.info(f"Processing started: {len(self._queue)} cards in queue{energy_note}")

    @staticmethod
    def _get_energy_level() -> str:
        """Get current energy level based on time of day."""
        from datetime import datetime as dt

        hour = dt.now().hour
        if hour < 14:
            return "HIGH"
        elif hour < 16:
            return "MEDIUM"
        else:
            return "LOW"

    def next_card(self) -> None:
        """Move to next card in queue."""
        # Save any notes for the current card
        self._save_current_notes()

        # Record the win and play audio feedback
        milestone = self._dopamine.record_win(WinType.CARD_PROCESSED)
        if milestone:
            self._audio.play_sound(Sound.STREAK)
        else:
            self._audio.play_sound(Sound.CARD_DONE)

        self._queue_index += 1
        if self._queue_index >= len(self._queue):
            self._show_queue_complete()
            return
        self._update_queue_label()
        self._show_current_card()

    def _show_current_card(self) -> None:
        """Display the current card from the queue."""
        if not self._card_frame:
            return

        # Clear existing card
        if self._card:
            self._card.destroy()
            self._card = None
        if self._status_label:
            self._status_label.pack_forget()

        if not self._queue or self._queue_index >= len(self._queue):
            if self._status_label:
                self._status_label.config(text="No cards in queue.")
                self._status_label.pack(expand=True)
            return

        prospect = self._queue[self._queue_index]

        # Load full data for the card
        company = self.db.get_company(prospect.company_id) if prospect.company_id else None
        if company is None:
            company = Company(name="Unknown", name_normalized="unknown")
        activities = self.db.get_activities(prospect.id, limit=20) if prospect.id else []
        intel = self.db.get_intel_nuggets(prospect.id) if prospect.id else []
        contact_methods = self.db.get_contact_methods(prospect.id) if prospect.id else []

        # Count other contacts at same company
        company_contacts = 0
        if prospect.company_id:
            others = self.db.get_prospects(company_id=prospect.company_id, limit=100)
            company_contacts = max(0, len(others) - 1)

        self._card = ProspectCard(self._card_frame)
        self._card.set_prospect(
            prospect=prospect,
            company=company,
            activities=activities,
            intel=intel,
            contact_methods=contact_methods,
            company_contacts=company_contacts,
        )
        self._card.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Clear notes field
        if self._notes_text:
            self._notes_text.delete("1.0", tk.END)

    def _show_queue_complete(self) -> None:
        """Show queue complete message."""
        if self._card:
            self._card.destroy()
            self._card = None

        self._audio.play_sound(Sound.DEAL_CLOSED)
        self._dopamine.check_achievement("queue_cleared")

        if self._status_label:
            streak = self._dopamine.get_streak()
            msg = "Queue complete! Great work."
            if streak >= 5:
                msg += f"\n\nStreak: {streak} cards processed."
            msg += "\n\nCheck the Calendar or Pipeline tabs."
            self._status_label.config(text=msg)
            self._status_label.pack(expand=True)
        self._update_queue_label()

    def _update_queue_label(self) -> None:
        """Update the queue position label."""
        if not self._queue_label:
            return
        total = len(self._queue)
        current = min(self._queue_index + 1, total)
        self._queue_label.config(text=f"Queue: {current} / {total} cards")

    def _save_current_notes(self) -> None:
        """Save notes for the current card if any were entered."""
        if not self._notes_text:
            return
        notes = self._notes_text.get("1.0", tk.END).strip()
        if not notes:
            return

        if self._queue and self._queue_index < len(self._queue):
            prospect = self._queue[self._queue_index]
            if prospect.id:
                activity = Activity(
                    prospect_id=prospect.id,
                    activity_type=ActivityType.NOTE,
                    notes=notes,
                    created_by="user",
                )
                self.db.create_activity(activity)
                logger.info(f"Notes saved for prospect {prospect.id}")

    def _quick_action(self) -> None:
        """Open quick action dialog for current card."""
        if not self._queue or self._queue_index >= len(self._queue):
            return
        prospect = self._queue[self._queue_index]
        if not prospect.id or not self.frame:
            return

        dialog = QuickActionDialog(self.frame, prospect.id, db=self.db)
        if dialog.show():
            self.next_card()

    def _toggle_deep(self) -> None:
        """Toggle between glance and deep dive view."""
        if not self._card:
            return
        if self._card._view_mode == "deep":
            self._card.set_view_mode("glance")
        else:
            self._card.set_view_mode("deep")

    def _edit_prospect(self) -> None:
        """Open edit dialog for current card."""
        if not self._queue or self._queue_index >= len(self._queue):
            return
        prospect = self._queue[self._queue_index]
        if not prospect.id or not self.frame:
            return

        from src.gui.dialogs.edit_prospect import EditProspectDialog

        dialog = EditProspectDialog(self.frame, prospect)
        if dialog.show():
            updated = dialog.get_updated_prospect()
            self.db.update_prospect(updated)
            self._show_current_card()  # Refresh the card

    def _skip_card(self) -> None:
        """Skip current card without any action."""
        if not self._queue or self._queue_index >= len(self._queue):
            return
        prospect = self._queue[self._queue_index]
        if prospect.id:
            activity = Activity(
                prospect_id=prospect.id,
                activity_type=ActivityType.SKIP,
                notes="Skipped during queue processing",
                created_by="user",
            )
            self.db.create_activity(activity)

        # Skip breaks the streak — no reward sound
        self._dopamine.break_streak()

        # Advance without calling next_card (which would record a win)
        self._save_current_notes()
        self._queue_index += 1
        if self._queue_index >= len(self._queue):
            self._show_queue_complete()
            return
        self._update_queue_label()
        self._show_current_card()

    def _quick_search(self) -> None:
        """Quick search for a prospect by name."""
        query = self._search_var.get().strip()
        if not query or not self.frame:
            return

        results = self.db.get_prospects(search_query=query, limit=10)
        if not results:
            messagebox.showinfo(
                "Search", f"No prospects found for '{query}'", parent=self.frame.winfo_toplevel()
            )
            return

        if len(results) == 1:
            # Single result — show it directly
            prospect = results[0]
            self._show_search_result(prospect)
        else:
            # Multiple results — show picker
            self._show_search_picker(results)

    def _show_search_result(self, prospect: Prospect) -> None:
        """Show a single search result in a detail dialog."""
        if not self.frame:
            return

        from src.gui.dialogs.edit_prospect import EditProspectDialog

        dialog = EditProspectDialog(self.frame, prospect)
        dialog.show()

    def _show_search_picker(self, results: list[Prospect]) -> None:
        """Show a picker dialog for multiple search results."""
        if not self.frame:
            return

        dialog = tk.Toplevel(self.frame)
        dialog.title("Search Results")
        dialog.geometry("400x300")
        dialog.transient(self.frame.winfo_toplevel())
        dialog.grab_set()

        tree = ttk.Treeview(
            dialog, columns=("ID", "Name", "Population"), show="headings", selectmode="browse"
        )
        tree.heading("ID", text="ID")
        tree.heading("Name", text="Name")
        tree.heading("Population", text="Population")
        tree.column("ID", width=50)
        tree.column("Name", width=200)
        tree.column("Population", width=120)

        for p in results:
            pop = p.population.value if p.population else ""
            tree.insert("", tk.END, values=(p.id, p.full_name, pop))

        tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        def on_select(event: object) -> None:
            sel = tree.selection()
            if sel:
                item = tree.item(sel[0])
                pid = int(item["values"][0])
                prospect = self.db.get_prospect(pid)
                dialog.destroy()
                if prospect:
                    self._show_search_result(prospect)

        tree.bind("<Double-Button-1>", on_select)
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=8)

"""Broken tab - Records missing phone/email.

Three-section workbench:
    1. Needs Confirmation — system found data, user confirms
    2. In Progress — system is still looking
    3. Manual Research Needed — system struck out, user researches
"""

import json
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Optional

from src.core.logging import get_logger
from src.core.phone import normalize_phone
from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    ContactMethod,
    ContactMethodType,
    Population,
    ResearchStatus,
)
from src.engine.populations import transition_prospect
from src.gui.tabs import TabBase
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)


class BrokenTab(TabBase):
    """Broken prospects management."""

    def __init__(self, parent: tk.Widget, db: Database):
        super().__init__(parent, db)
        self._confirm_tree: Optional[ttk.Treeview] = None
        self._progress_tree: Optional[ttk.Treeview] = None
        self._manual_tree: Optional[ttk.Treeview] = None
        self._header_label: Optional[tk.Label] = None
        self._task_lookup: dict[int, Any] = {}
        self._create_ui()

    def _create_ui(self) -> None:
        """Create broken tab UI."""
        if not self.frame:
            return

        # Header with count
        self._header_label = tk.Label(
            self.frame,
            text="Broken Records",
            font=("Segoe UI", 14, "bold"),
            bg=COLORS["bg"],
            fg=COLORS["fg"],
        )
        self._header_label.pack(padx=12, pady=(8, 4), anchor="w")

        # Three sections in a scrollable area
        canvas = tk.Canvas(self.frame, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=COLORS["bg"])

        scroll_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Section 1: Needs Confirmation
        self._create_section(
            scroll_frame, "NEEDS CONFIRMATION", "System found data — confirm or reject", "confirm"
        )

        # Section 2: In Progress
        self._create_section(scroll_frame, "IN PROGRESS", "System is still searching", "progress")

        # Section 3: Manual Research Needed
        self._create_section(
            scroll_frame, "MANUAL RESEARCH NEEDED", "System struck out — your turn", "manual"
        )

    def _create_section(
        self, parent: tk.Widget, title: str, subtitle: str, section_key: str
    ) -> None:
        """Create a section with treeview."""
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.pack(fill=tk.X, padx=4, pady=8)

        tk.Label(
            frame,
            text=subtitle,
            font=FONTS["small"],
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).pack(anchor="w", pady=(0, 4))

        columns = ("ID", "Name", "Company", "Missing")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=6)
        tree.heading("ID", text="ID")
        tree.heading("Name", text="Name")
        tree.heading("Company", text="Company")
        tree.heading("Missing", text="Missing")

        tree.column("ID", width=50)
        tree.column("Name", width=180)
        tree.column("Company", width=160)
        tree.column("Missing", width=160)

        tree.pack(fill=tk.X)

        # Action buttons per section
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(4, 0))

        if section_key == "confirm":
            self._confirm_tree = tree
            ttk.Button(
                btn_frame,
                text="View Findings",
                command=self._view_findings,
            ).pack(side=tk.LEFT, padx=4)
            ttk.Button(
                btn_frame,
                text="Confirm Selected",
                command=self._confirm_selected,
            ).pack(side=tk.LEFT, padx=4)
            ttk.Button(
                btn_frame,
                text="Reject Selected",
                command=self._reject_selected,
            ).pack(side=tk.LEFT, padx=4)
        elif section_key == "progress":
            self._progress_tree = tree
        elif section_key == "manual":
            self._manual_tree = tree
            ttk.Button(
                btn_frame,
                text="Add Contact Method",
                command=self._add_contact_method,
            ).pack(side=tk.LEFT, padx=4)
            ttk.Button(
                btn_frame,
                text="Mark as Researched",
                command=self._mark_researched,
            ).pack(side=tk.LEFT, padx=4)

    def refresh(self) -> None:
        """Reload broken data from database."""
        conn = self.db._get_connection()

        # Count total broken
        broken_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM prospects WHERE population = ?",
            (Population.BROKEN.value,),
        ).fetchone()
        total = broken_count["cnt"] if broken_count else 0

        # Get research tasks
        tasks_by_status: dict[str, list] = {
            ResearchStatus.COMPLETED.value: [],
            ResearchStatus.IN_PROGRESS.value: [],
            ResearchStatus.PENDING.value: [],
            ResearchStatus.FAILED.value: [],
        }

        tasks = conn.execute(
            """SELECT rt.*, p.first_name, p.last_name, p.population,
                      c.name as company_name
               FROM research_queue rt
               JOIN prospects p ON rt.prospect_id = p.id
               LEFT JOIN companies c ON p.company_id = c.id
               WHERE p.population = ?
               ORDER BY rt.priority DESC""",
            (Population.BROKEN.value,),
        ).fetchall()

        self._task_lookup = {}
        for task in tasks:
            status = task["status"]
            if status in tasks_by_status:
                tasks_by_status[status].append(task)
            try:
                self._task_lookup[int(task["prospect_id"])] = task
            except Exception:
                continue

        # Also get broken prospects without research tasks
        all_broken = conn.execute(
            """SELECT p.id, p.first_name, p.last_name, c.name as company_name
               FROM prospects p
               LEFT JOIN companies c ON p.company_id = c.id
               WHERE p.population = ?""",
            (Population.BROKEN.value,),
        ).fetchall()

        researched_ids = {t["prospect_id"] for t in tasks}
        no_task = [r for r in all_broken if r["id"] not in researched_ids]

        # Determine what's missing for each broken prospect
        def get_missing(prospect_id: int) -> str:
            methods = self.db.get_contact_methods(prospect_id)
            has_email = any(m.type and m.type.value == "email" for m in methods)
            has_phone = any(m.type and m.type.value == "phone" for m in methods)
            parts = []
            if not has_email:
                parts.append("email")
            if not has_phone:
                parts.append("phone")
            return ", ".join(parts) if parts else "unknown"

        # Update header
        confirm_count = len(tasks_by_status[ResearchStatus.COMPLETED.value])
        progress_count = len(tasks_by_status[ResearchStatus.IN_PROGRESS.value])
        manual_count = len(tasks_by_status[ResearchStatus.FAILED.value]) + len(no_task)

        if self._header_label:
            self._header_label.config(
                text=f"Broken Records: {total} total — "
                f"{confirm_count} ready, {progress_count} in progress, {manual_count} need you"
            )

        # Populate: Needs Confirmation (completed research tasks)
        self._populate_tree(
            self._confirm_tree,
            tasks_by_status[ResearchStatus.COMPLETED.value],
            get_missing,
        )

        # Populate: In Progress
        in_progress = (
            tasks_by_status[ResearchStatus.IN_PROGRESS.value]
            + tasks_by_status[ResearchStatus.PENDING.value]
        )
        self._populate_tree(self._progress_tree, in_progress, get_missing)

        # Populate: Manual Research Needed
        failed_tasks = tasks_by_status[ResearchStatus.FAILED.value]
        manual_rows = failed_tasks + [
            {
                "prospect_id": r["id"],
                "first_name": r["first_name"],
                "last_name": r["last_name"],
                "company_name": r["company_name"],
            }
            for r in no_task
        ]
        self._populate_tree(self._manual_tree, manual_rows, get_missing)

    def _populate_tree(
        self, tree: Optional[ttk.Treeview], rows: list, get_missing_fn: object
    ) -> None:
        """Populate a treeview with prospect data."""
        if not tree:
            return
        tree.delete(*tree.get_children())

        for row in rows:
            row_keys = row.keys()
            pid = (
                row["prospect_id"]
                if "prospect_id" in row_keys
                else (row["id"] if "id" in row_keys else 0)
            )
            name = f"{row['first_name']} {row['last_name']}"
            company = (row["company_name"] or "") if "company_name" in row_keys else ""
            missing = get_missing_fn(pid) if callable(get_missing_fn) else ""
            tree.insert("", tk.END, values=(pid, name, company, missing))

    def on_activate(self) -> None:
        """Called when this tab becomes visible."""
        self.refresh()

    def show_needs_confirmation(self) -> None:
        """Show records with research findings to confirm."""
        self.refresh()

    def show_in_progress(self) -> None:
        """Show records currently being researched."""
        self.refresh()

    def show_manual_needed(self) -> None:
        """Show records needing manual research."""
        self.refresh()

    def _confirm_selected(self) -> None:
        """Confirm research findings and graduate to unengaged."""
        if not self._confirm_tree or not self.frame:
            return
        selected = self._confirm_tree.selection()
        if not selected:
            messagebox.showinfo(
                "Info", "Select a record to confirm.", parent=self.frame.winfo_toplevel()
            )
            return

        confirmed = 0
        still_missing = 0
        no_findings = 0
        applied_findings = 0

        for item in selected:
            values = self._confirm_tree.item(item)["values"]
            pid = int(values[0])
            findings = self._get_findings(pid)
            if not findings:
                no_findings += 1
                continue

            applied_findings += self._apply_findings(pid, findings)

            if self._is_complete(pid):
                try:
                    transition_prospect(
                        self.db,
                        pid,
                        Population.UNENGAGED,
                        reason="Research confirmed — data complete",
                    )
                    confirmed += 1
                    logger.info(f"Confirmed broken prospect {pid} -> unengaged")
                except Exception as e:
                    logger.error(f"Failed to confirm prospect {pid}: {e}")
            else:
                still_missing += 1

        if confirmed or still_missing or no_findings:
            messagebox.showinfo(
                "Confirmation Summary",
                f"Applied findings: {applied_findings}\n"
                f"Moved to unengaged: {confirmed}\n"
                f"Still missing data: {still_missing}\n"
                f"No findings to apply: {no_findings}",
                parent=self.frame.winfo_toplevel(),
            )

        self.refresh()

    def _reject_selected(self) -> None:
        """Reject research findings."""
        if not self._confirm_tree or not self.frame:
            return
        selected = self._confirm_tree.selection()
        if not selected:
            messagebox.showinfo(
                "Info", "Select a record to reject.", parent=self.frame.winfo_toplevel()
            )
            return

        # Move back to manual research needed
        for item in selected:
            values = self._confirm_tree.item(item)["values"]
            pid = int(values[0])
            # Update research task to failed
            tasks = self.db.get_research_tasks(status=ResearchStatus.COMPLETED.value)
            for task in tasks:
                if task.prospect_id == pid:
                    task.status = ResearchStatus.FAILED
                    conn = self.db._get_connection()
                    conn.execute(
                        "UPDATE research_queue SET status = ? WHERE id = ?",
                        (ResearchStatus.FAILED.value, task.id),
                    )
                    conn.commit()
                    break
            logger.info(f"Rejected research for prospect {pid}")

        self.refresh()

    def _mark_researched(self) -> None:
        """Mark a manually researched record for re-evaluation."""
        if not self._manual_tree or not self.frame:
            return
        selected = self._manual_tree.selection()
        if not selected:
            messagebox.showinfo(
                "Info", "Select a record first.", parent=self.frame.winfo_toplevel()
            )
            return

        for item in selected:
            values = self._manual_tree.item(item)["values"]
            pid = int(values[0])
            # Check if data is now complete
            methods = self.db.get_contact_methods(pid)
            has_email = any(m.type and m.type.value == "email" for m in methods)
            has_phone = any(m.type and m.type.value == "phone" for m in methods)

            if has_email and has_phone:
                try:
                    transition_prospect(
                        self.db,
                        pid,
                        Population.UNENGAGED,
                        reason="Manual research complete — data complete",
                    )
                    logger.info(f"Manually researched prospect {pid} -> unengaged")
                except Exception as e:
                    logger.error(f"Failed to transition prospect {pid}: {e}")
            else:
                messagebox.showinfo(
                    "Still Incomplete",
                    f"Prospect still missing: {'email' if not has_email else ''}"
                    f"{' and ' if not has_email and not has_phone else ''}"
                    f"{'phone' if not has_phone else ''}.\n\n"
                    "Add contact methods first, then try again.",
                    parent=self.frame.winfo_toplevel(),
                )

        self.refresh()

    def _view_findings(self) -> None:
        """Show research findings for the selected record."""
        if not self._confirm_tree or not self.frame:
            return
        selected = self._confirm_tree.selection()
        if not selected:
            messagebox.showinfo(
                "Info", "Select a record to view findings.", parent=self.frame.winfo_toplevel()
            )
            return
        if len(selected) > 1:
            messagebox.showinfo(
                "Info",
                "Select a single record to view findings.",
                parent=self.frame.winfo_toplevel(),
            )
            return

        values = self._confirm_tree.item(selected[0])["values"]
        pid = int(values[0])
        findings = self._get_findings(pid)
        if not findings:
            messagebox.showinfo(
                "No Findings",
                "No research findings available for this record.",
                parent=self.frame.winfo_toplevel(),
            )
            return

        dialog = tk.Toplevel(self.frame)
        dialog.title("Research Findings")
        dialog.geometry("520x360")
        dialog.transient(self.frame.winfo_toplevel())

        text = tk.Text(dialog, wrap=tk.WORD, font=FONTS["small"])
        text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        for i, finding in enumerate(findings, start=1):
            field = finding.get("field", "")
            value = finding.get("value", "")
            confidence = finding.get("confidence", "")
            source = finding.get("source", "")
            text.insert(
                tk.END,
                f"{i}. {field}: {value}\n"
                f"   confidence: {confidence}\n"
                f"   source: {source}\n\n",
            )

        text.config(state="disabled")
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=(0, 8))

    def _add_contact_method(self) -> None:
        """Add a contact method to the selected broken prospect."""
        if not self._manual_tree or not self.frame:
            return
        selected = self._manual_tree.selection()
        if not selected:
            messagebox.showinfo(
                "Info", "Select a record first.", parent=self.frame.winfo_toplevel()
            )
            return

        values = self._manual_tree.item(selected[0])["values"]
        pid = int(values[0])
        methods = self.db.get_contact_methods(pid)

        from src.gui.dialogs.contact_method import ContactMethodDialog

        dialog = ContactMethodDialog(self.frame, pid, methods)
        method = dialog.show()
        if not method:
            return

        # If new method is primary, unset existing primaries of the same type
        if method.is_primary:
            for m in methods:
                if m.type == method.type and m.is_primary:
                    m.is_primary = False
                    self.db.update_contact_method(m)

        self.db.create_contact_method(method)
        self.refresh()

    def _get_findings(self, prospect_id: int) -> list[dict[str, str]]:
        """Get parsed research findings for a prospect."""
        task = self._task_lookup.get(prospect_id)
        if not task:
            return []
        findings_raw = task["findings"] if "findings" in task.keys() else None
        if not findings_raw:
            return []
        try:
            data = json.loads(findings_raw)
        except (TypeError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        findings: list[dict[str, str]] = []
        for item in data:
            if isinstance(item, dict):
                findings.append(item)
        return findings

    def _apply_findings(self, prospect_id: int, findings: list[dict[str, str]]) -> int:
        """Apply research findings to contact methods."""
        existing = self.db.get_contact_methods(prospect_id)
        existing_emails = {m.value.lower() for m in existing if m.type == ContactMethodType.EMAIL}
        existing_phones = {
            normalize_phone(m.value) for m in existing if m.type == ContactMethodType.PHONE
        }

        has_primary_email = any(
            m.type == ContactMethodType.EMAIL and m.is_primary for m in existing
        )
        has_primary_phone = any(
            m.type == ContactMethodType.PHONE and m.is_primary for m in existing
        )

        added = 0
        for finding in findings:
            field = str(finding.get("field", "")).lower().strip()
            value = str(finding.get("value", "")).strip()
            if not value:
                continue

            confidence = str(finding.get("confidence", "")).lower().strip()
            source = str(finding.get("source", "research")).strip()

            if field == "email":
                email = value.lower()
                if email in existing_emails:
                    continue
                method = ContactMethod(
                    prospect_id=prospect_id,
                    type=ContactMethodType.EMAIL,
                    value=email,
                    is_primary=not has_primary_email,
                    source=f"research:{source}",
                    confidence_score=self._confidence_score(confidence),
                )
                self.db.create_contact_method(method)
                has_primary_email = True
                existing_emails.add(email)
            elif field == "phone":
                phone = normalize_phone(value)
                if not phone or phone in existing_phones:
                    continue
                method = ContactMethod(
                    prospect_id=prospect_id,
                    type=ContactMethodType.PHONE,
                    value=phone,
                    is_primary=not has_primary_phone,
                    source=f"research:{source}",
                    confidence_score=self._confidence_score(confidence),
                )
                self.db.create_contact_method(method)
                has_primary_phone = True
                existing_phones.add(phone)
            else:
                continue

            activity = Activity(
                prospect_id=prospect_id,
                activity_type=ActivityType.ENRICHMENT,
                notes=(
                    f"Confirmed research {field}: {value} "
                    f"(source: {source}, confidence: {confidence})"
                ),
                created_by="user",
            )
            self.db.create_activity(activity)
            added += 1

        return added

    def _is_complete(self, prospect_id: int) -> bool:
        """Check if prospect has both email and phone."""
        methods = self.db.get_contact_methods(prospect_id)
        has_email = any(m.type == ContactMethodType.EMAIL for m in methods)
        has_phone = any(m.type == ContactMethodType.PHONE for m in methods)
        return has_email and has_phone

    def _confidence_score(self, confidence: str) -> int:
        """Map confidence label to score."""
        if confidence == "high":
            return 90
        if confidence == "medium":
            return 70
        if confidence == "low":
            return 40
        return 50

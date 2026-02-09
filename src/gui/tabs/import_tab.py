"""Import tab - File upload, mapping, and preview."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.intake import ImportPreview, ImportRecord, IntakeFunnel
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class ImportTab(TabBase):
    """Import functionality — CSV/XLSX file upload, preview, and commit."""

    def __init__(self, parent: tk.Widget, db: Database):
        super().__init__(parent, db)
        self._preview: Optional[ImportPreview] = None
        self._records: list[ImportRecord] = []
        self._file_path: Optional[str] = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.frame = ttk.Frame(self.parent)  # type: ignore[assignment]

        # --- Header ---
        header = ttk.Frame(self.frame)
        header.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(header, text="Import", font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)

        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)

        # --- File selection ---
        file_frame = ttk.LabelFrame(self.frame, text="1. Select File", padding=10)
        file_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        file_row = ttk.Frame(file_frame)
        file_row.pack(fill=tk.X)
        self._file_var = tk.StringVar(value="No file selected")
        ttk.Label(file_row, textvariable=self._file_var, style="Muted.TLabel").pack(
            side=tk.LEFT, fill=tk.X, expand=True,
        )
        ttk.Button(file_row, text="Choose File...", command=self.select_file).pack(side=tk.RIGHT)

        # --- Preview area ---
        preview_frame = ttk.LabelFrame(self.frame, text="2. Preview", padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self._preview_text = tk.Text(
            preview_frame, height=14, font=("Consolas", 9), wrap=tk.WORD,
            state=tk.DISABLED, bg="#ffffff",
        )
        scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self._preview_text.yview)
        self._preview_text.configure(yscrollcommand=scrollbar.set)
        self._preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Import button ---
        action_frame = ttk.Frame(self.frame)
        action_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self._import_btn = ttk.Button(
            action_frame, text="Import", style="Accent.TButton",
            command=self.execute_import, state=tk.DISABLED,
        )
        self._import_btn.pack(side=tk.RIGHT)

        self._status_var = tk.StringVar(value="")
        ttk.Label(action_frame, textvariable=self._status_var, style="Muted.TLabel").pack(
            side=tk.LEFT,
        )

        # --- History ---
        hist_frame = ttk.LabelFrame(self.frame, text="Import History", padding=10)
        hist_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self._history_text = tk.Text(
            hist_frame, height=4, font=("Consolas", 9), wrap=tk.WORD,
            state=tk.DISABLED, bg="#ffffff",
        )
        self._history_text.pack(fill=tk.X)

    # ------------------------------------------------------------------
    # TabBase
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._load_history()

    def on_activate(self) -> None:
        self.refresh()

    # ------------------------------------------------------------------
    # File selection & parsing
    # ------------------------------------------------------------------

    def select_file(self) -> None:
        """Open file dialog to choose a CSV/XLSX file."""
        path = filedialog.askopenfilename(
            title="Select import file",
            filetypes=[
                ("CSV files", "*.csv"),
                ("Excel files", "*.xlsx"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self._file_path = path
        self._file_var.set(Path(path).name)
        self._parse_file(path)

    def _parse_file(self, path: str) -> None:
        """Parse the file and run preview analysis."""
        from src.integrations.csv_importer import parse_csv_file

        try:
            self._records = parse_csv_file(path)
        except Exception as e:
            messagebox.showerror("Parse Error", f"Failed to read file:\n{e}")
            self._records = []
            return

        self.preview_import()

    def show_mapping(self) -> None:
        """Show column mapping interface (currently auto-mapped)."""
        messagebox.showinfo("Column Mapping", "Columns are auto-mapped from file headers.")

    def preview_import(self) -> None:
        """Analyze records and show preview."""
        if not self._records:
            return

        funnel = IntakeFunnel(self.db)
        filename = Path(self._file_path).name if self._file_path else "unknown"
        try:
            self._preview = funnel.analyze(self._records, source_name="Import Tab", filename=filename)
        except Exception as e:
            messagebox.showerror("Analysis Error", str(e))
            return

        # Display preview
        p = self._preview
        lines = [
            f"File: {filename}",
            f"Total records: {len(self._records)}",
            "",
            f"New prospects:     {len(p.new_records)}",
            f"Merge (existing):  {len(p.merge_records)}",
            f"Needs review:      {len(p.needs_review)}",
            f"Blocked (DNC):     {len(p.blocked_dnc)}",
            f"Incomplete:        {len(p.incomplete)}",
        ]

        self._preview_text.configure(state=tk.NORMAL)
        self._preview_text.delete("1.0", tk.END)
        self._preview_text.insert("1.0", "\n".join(lines))
        self._preview_text.configure(state=tk.DISABLED)

        self._import_btn.configure(state=tk.NORMAL)
        self._status_var.set("Review the preview, then click Import.")

    def execute_import(self) -> None:
        """Commit the previewed import."""
        if not self._preview:
            return

        confirm = messagebox.askyesno(
            "Confirm Import",
            f"Import {len(self._preview.new_records)} new, "
            f"merge {len(self._preview.merge_records)} existing?",
        )
        if not confirm:
            return

        funnel = IntakeFunnel(self.db)
        try:
            result = funnel.commit(self._preview)
            self._status_var.set(
                f"Imported {result.imported_count}, merged {result.merged_count}, "
                f"broken {result.broken_count}"
            )
            self._import_btn.configure(state=tk.DISABLED)
            self._preview = None
            self._load_history()
            logger.info(
                "Import completed",
                extra={"context": {
                    "imported": result.imported_count,
                    "merged": result.merged_count,
                }},
            )
        except Exception as e:
            messagebox.showerror("Import Error", str(e))

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def _load_history(self) -> None:
        """Load recent import history."""
        try:
            sources = self.db.get_import_sources(limit=10)
            lines = []
            for s in sources:
                lines.append(
                    f"{s.created_at:%Y-%m-%d %H:%M}  {s.filename}  "
                    f"({s.imported_count} imported, {s.duplicate_count} dupes)"
                )
            text = "\n".join(lines) if lines else "No imports yet."
        except Exception:
            text = "Failed to load history."

        self._history_text.configure(state=tk.NORMAL)
        self._history_text.delete("1.0", tk.END)
        self._history_text.insert("1.0", text)
        self._history_text.configure(state=tk.DISABLED)

"""Import tab - File upload, mapping, and preview."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from src.core.logging import get_logger
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class ImportTab(TabBase):
    """Import functionality."""

    def __init__(self, parent: tk.Widget, db: object):
        super().__init__(parent, db)
        self._selected_file: Optional[str] = None
        self._parse_result = None
        self._mapping_widgets = {}
        self._create_ui()

    def _create_ui(self) -> None:
        """Create import tab UI."""
        if not self.frame:
            return
            
        # Create main container with scrollbar
        canvas = tk.Canvas(self.frame)
        scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # File selection section
        file_frame = ttk.LabelFrame(scrollable_frame, text="File Selection", padding=10)
        file_frame.pack(fill=tk.X, padx=10, pady=5)
        
        select_btn = ttk.Button(file_frame, text="Select File", command=self.select_file)
        select_btn.pack(side=tk.LEFT, padx=5)
        
        self._file_label = ttk.Label(file_frame, text="No file selected")
        self._file_label.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Preset selection
        preset_frame = ttk.Frame(scrollable_frame)
        preset_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(preset_frame, text="Auto-detect preset:").pack(side=tk.LEFT, padx=5)
        self._preset_var = tk.StringVar(value="None")
        self._preset_combo = ttk.Combobox(
            preset_frame,
            textvariable=self._preset_var,
            values=["None", "phoneburner", "aapl"],
            state="readonly",
            width=20
        )
        self._preset_combo.pack(side=tk.LEFT, padx=5)
        
        # Column mapping section
        self._mapping_frame = ttk.LabelFrame(scrollable_frame, text="Column Mapping", padding=10)
        self._mapping_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        no_file_label = ttk.Label(self._mapping_frame, text="Select a file to see column mappings")
        no_file_label.pack(pady=20)
        
        # Preview and import buttons
        action_frame = ttk.Frame(scrollable_frame)
        action_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self._preview_btn = ttk.Button(
            action_frame,
            text="Preview Import",
            command=self.preview_import,
            state="disabled"
        )
        self._preview_btn.pack(side=tk.LEFT, padx=5)
        
        self._import_btn = ttk.Button(
            action_frame,
            text="Execute Import",
            command=self.execute_import,
            state="disabled"
        )
        self._import_btn.pack(side=tk.LEFT, padx=5)
        
        # Import history section
        history_frame = ttk.LabelFrame(scrollable_frame, text="Import History", padding=10)
        history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self._history_text = tk.Text(history_frame, height=8, state="disabled")
        self._history_text.pack(fill=tk.BOTH, expand=True)
        
        history_scroll = ttk.Scrollbar(history_frame, command=self._history_text.yview)
        history_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._history_text.config(yscrollcommand=history_scroll.set)

    def refresh(self) -> None:
        """Reload import tab state."""
        self._load_import_history()
        logger.info("Import tab refreshed")

    def on_activate(self) -> None:
        """Called when this tab becomes visible."""
        self.refresh()

    def select_file(self) -> None:
        """Open file dialog."""
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("CSV Files", "*.csv"),
                ("Excel Files", "*.xlsx"),
                ("All Files", "*.*"),
            ]
        )
        if file_path:
            self._selected_file = file_path
            self._file_label.config(text=Path(file_path).name)
            logger.info(f"Import file selected: {file_path}")
            self._load_file()

    def _load_file(self) -> None:
        """Load and parse the selected file."""
        if not self._selected_file:
            return
            
        try:
            from src.integrations.csv_importer import CSVImporter
            
            importer = CSVImporter()
            self._parse_result = importer.parse_file(Path(self._selected_file))
            
            # Update preset dropdown
            if self._parse_result.detected_preset:
                self._preset_var.set(self._parse_result.detected_preset)
            
            # Show column mappings
            self._show_mapping_ui()
            
            # Enable buttons
            self._preview_btn.config(state="normal")
            self._import_btn.config(state="normal")
            
            logger.info(f"File parsed: {self._parse_result.total_rows} rows, {len(self._parse_result.headers)} columns")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse file: {e}")
            logger.error(f"File parsing failed: {e}")

    def _show_mapping_ui(self) -> None:
        """Show column mapping interface."""
        # Clear existing widgets
        for widget in self._mapping_frame.winfo_children():
            widget.destroy()
        
        self._mapping_widgets = {}
        
        if not self._parse_result:
            return
        
        # Create mapping dropdowns for each required field
        required_fields = [
            ("first_name", "First Name"),
            ("last_name", "Last Name"),
            ("email", "Email"),
            ("phone", "Phone"),
            ("company_name", "Company"),
            ("title", "Title"),
            ("state", "State"),
        ]
        
        headers = [""] + self._parse_result.headers
        
        for i, (field_key, field_label) in enumerate(required_fields):
            ttk.Label(self._mapping_frame, text=f"{field_label}:").grid(
                row=i, column=0, sticky="w", padx=5, pady=3
            )
            
            var = tk.StringVar(value="")
            combo = ttk.Combobox(
                self._mapping_frame,
                textvariable=var,
                values=headers,
                state="readonly",
                width=30
            )
            combo.grid(row=i, column=1, sticky="ew", padx=5, pady=3)
            self._mapping_widgets[field_key] = var
            
            # Auto-select matching column if found
            for header in self._parse_result.headers:
                if field_label.lower() in header.lower() or field_key in header.lower():
                    var.set(header)
                    break
        
        self._mapping_frame.columnconfigure(1, weight=1)

    def preview_import(self) -> None:
        """Show import preview dialog."""
        if not self._selected_file or not self._parse_result:
            messagebox.showwarning("Warning", "No file selected for preview")
            return
        
        try:
            # Build mapping
            mapping = {}
            for field_key, var in self._mapping_widgets.items():
                if var.get():
                    mapping[field_key] = var.get()
            
            if not mapping:
                messagebox.showwarning("Warning", "No columns mapped")
                return
            
            # Get import records
            from src.integrations.csv_importer import CSVImporter
            importer = CSVImporter()
            records = importer.apply_mapping(
                Path(self._selected_file),
                mapping,
                self._preset_var.get() if self._preset_var.get() != "None" else None
            )
            
            # Analyze with intake funnel
            from src.db.intake import IntakeFunnel
            funnel = IntakeFunnel(self.db)
            preview = funnel.analyze(
                records,
                source_name="manual_import",
                filename=Path(self._selected_file).name
            )
            
            # Show preview dialog
            self._show_preview_dialog(preview)
            
            logger.info(f"Preview generated: {len(records)} records analyzed")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate preview: {e}")
            logger.error(f"Preview generation failed: {e}")

    def _show_preview_dialog(self, preview) -> None:
        """Display import preview dialog."""
        dialog = tk.Toplevel(self.frame)
        dialog.title("Import Preview")
        dialog.geometry("600x500")
        
        # Summary
        summary_frame = ttk.LabelFrame(dialog, text="Summary", padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=5)
        
        summary_text = f"""
New prospects: {len(preview.new_records)}
Will be merged: {len(preview.merge_records)}
Needs review: {len(preview.needs_review)}
Blocked (DNC): {len(preview.blocked_dnc)}
Incomplete: {len(preview.incomplete)}
        """
        ttk.Label(summary_frame, text=summary_text, justify="left").pack()
        
        # Details
        details_frame = ttk.LabelFrame(dialog, text="Details (First 5)", padding=10)
        details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        details_text = tk.Text(details_frame, height=20)
        details_text.pack(fill=tk.BOTH, expand=True)
        
        # Show first 5 new records
        for i, record in enumerate(preview.new_records[:5]):
            details_text.insert(tk.END, f"\n{i+1}. {record.first_name} {record.last_name}\n")
            details_text.insert(tk.END, f"   Company: {record.company_name}\n")
            details_text.insert(tk.END, f"   Email: {record.email}\n")
            if record.phone:
                details_text.insert(tk.END, f"   Phone: {record.phone}\n")
        
        # Highlight DNC blocks in red
        if preview.blocked_dnc:
            details_text.insert(tk.END, f"\n\n⚠️ BLOCKED (DNC):\n", "warning")
            for i, record in enumerate(preview.blocked_dnc[:5]):
                details_text.insert(tk.END, f"{i+1}. {record.first_name} {record.last_name} - {record.email or record.phone}\n", "dnc")
            
            details_text.tag_config("dnc", foreground="red")
            details_text.tag_config("warning", foreground="orange", font=("", 10, "bold"))
        
        details_text.config(state="disabled")
        
        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

    def execute_import(self) -> None:
        """Execute the import."""
        if not self._selected_file or not self._parse_result:
            messagebox.showwarning("Warning", "No file selected for import")
            return
        
        try:
            # Build mapping
            mapping = {}
            for field_key, var in self._mapping_widgets.items():
                if var.get():
                    mapping[field_key] = var.get()
            
            if not mapping:
                messagebox.showwarning("Warning", "No columns mapped")
                return
            
            # Confirm import
            if not messagebox.askyesno("Confirm Import", 
                f"Import {self._parse_result.total_rows} records from {Path(self._selected_file).name}?"):
                return
            
            # Get import records
            from src.integrations.csv_importer import CSVImporter
            importer = CSVImporter()
            records = importer.apply_mapping(
                Path(self._selected_file),
                mapping,
                self._preset_var.get() if self._preset_var.get() != "None" else None
            )
            
            # Analyze and commit
            from src.db.intake import IntakeFunnel
            funnel = IntakeFunnel(self.db)
            preview = funnel.analyze(
                records,
                source_name="manual_import",
                filename=Path(self._selected_file).name
            )
            
            result = funnel.commit(preview)
            
            # Show success message
            messagebox.showinfo("Import Complete",
                f"Import successful!\n\n"
                f"Created: {result.created_count}\n"
                f"Merged: {result.merged_count}\n"
                f"Blocked (DNC): {result.blocked_dnc_count}")
            
            logger.info(f"Import completed: {result.created_count} created, {result.merged_count} merged")
            
            # Refresh history
            self.refresh()
            
            # Clear selection
            self._selected_file = None
            self._parse_result = None
            self._file_label.config(text="No file selected")
            self._preview_btn.config(state="disabled")
            self._import_btn.config(state="disabled")
            self._show_mapping_ui()
            
        except Exception as e:
            messagebox.showerror("Error", f"Import failed: {e}")
            logger.error(f"Import execution failed: {e}")

    def _load_import_history(self) -> None:
        """Load import history from database."""
        try:
            from src.db.models import ActivityType
            
            # Get recent import activities
            activities = []
            prospects = self.db.get_prospects(limit=100)
            for prospect in prospects:
                acts = self.db.get_activities(prospect.id, limit=5)
                for act in acts:
                    if act.activity_type == ActivityType.IMPORT:
                        activities.append(act)
            
            # Sort by date and take latest 10
            activities.sort(key=lambda a: a.timestamp or "", reverse=True)
            activities = activities[:10]
            
            # Display
            self._history_text.config(state="normal")
            self._history_text.delete("1.0", tk.END)
            
            if activities:
                for act in activities:
                    timestamp = act.timestamp.strftime("%Y-%m-%d %H:%M") if act.timestamp else "Unknown"
                    self._history_text.insert(tk.END, f"{timestamp} - {act.notes or 'Import'}\n")
            else:
                self._history_text.insert(tk.END, "No import history yet")
            
            self._history_text.config(state="disabled")
        except Exception as e:
            logger.warning(f"Failed to load import history: {e}")

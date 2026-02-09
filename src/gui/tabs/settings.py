"""Settings tab - Configuration, backup, recovery, service status.

Includes a service readiness panel that shows which external
integrations are configured and which credentials are missing.
This is the first place the user looks when something isn't working.
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src.core.logging import get_logger
from src.db.database import Database
from src.gui.tabs import TabBase

logger = get_logger(__name__)


class SettingsTab(TabBase):
    """Application settings.

    Shows service readiness, backup controls, and app info.
    """

    def __init__(self, parent: tk.Widget, db: Database):
        super().__init__(parent, db)
        self._build_ui()

    def _build_ui(self) -> None:
        self.frame = ttk.Frame(self.parent)  # type: ignore[assignment]

        # --- Header ---
        header = ttk.Frame(self.frame)
        header.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(header, text="Settings", font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)

        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)

        # --- Service readiness ---
        svc_frame = ttk.LabelFrame(self.frame, text="Service Readiness", padding=10)
        svc_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self._service_text = tk.Text(
            svc_frame, height=8, font=("Consolas", 10), wrap=tk.WORD,
            state=tk.DISABLED, bg="#ffffff", relief=tk.FLAT,
        )
        self._service_text.pack(fill=tk.X)

        # --- Backup controls ---
        backup_frame = ttk.LabelFrame(self.frame, text="Database Backup", padding=10)
        backup_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        btn_row = ttk.Frame(backup_frame)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="Create Backup Now", command=self.create_backup).pack(
            side=tk.LEFT, padx=(0, 8),
        )
        ttk.Button(btn_row, text="Restore from Backup...", command=self.restore_backup).pack(
            side=tk.LEFT,
        )

        self._backup_status = tk.StringVar(value="")
        ttk.Label(backup_frame, textvariable=self._backup_status, style="Muted.TLabel").pack(
            fill=tk.X, pady=(8, 0),
        )

        # --- About ---
        about_frame = ttk.LabelFrame(self.frame, text="About", padding=10)
        about_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(about_frame, text="IronLung 3 v0.1.0").pack(anchor=tk.W)
        ttk.Label(
            about_frame, text="ADHD-Optimized Sales Pipeline Management", style="Muted.TLabel",
        ).pack(anchor=tk.W)
        ttk.Label(about_frame, text="Nexys LLC", style="Muted.TLabel").pack(anchor=tk.W)

        # --- Re-run setup ---
        ttk.Button(
            self.frame, text="Re-run Setup Wizard...", command=self._rerun_setup,
        ).pack(padx=10, pady=(0, 10), anchor=tk.W)

    # ------------------------------------------------------------------
    # TabBase
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        text = self.get_service_readiness()
        self._service_text.configure(state=tk.NORMAL)
        self._service_text.delete("1.0", tk.END)
        self._service_text.insert("1.0", text)
        self._service_text.configure(state=tk.DISABLED)

    def on_activate(self) -> None:
        self.refresh()

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    def create_backup(self) -> None:
        """Trigger manual backup."""
        from src.db.backup import BackupManager

        try:
            mgr = BackupManager()
            mgr.create_backup(label="manual")
            self._backup_status.set("Backup created successfully.")
            logger.info("Manual backup created from Settings tab")
        except Exception as e:
            self._backup_status.set(f"Backup failed: {e}")
            messagebox.showerror("Backup Error", str(e))

    def restore_backup(self) -> None:
        """Open restore dialog."""
        path = filedialog.askopenfilename(
            title="Select backup to restore",
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")],
        )
        if not path:
            return
        confirm = messagebox.askyesno(
            "Confirm Restore",
            f"Restore from:\n{path}\n\nThis will replace the current database. Continue?",
        )
        if not confirm:
            return

        from src.db.backup import BackupManager

        try:
            mgr = BackupManager()
            mgr.restore_backup(path)
            self._backup_status.set(f"Restored from {path}. Restart recommended.")
            logger.info("Database restored", extra={"context": {"path": path}})
        except Exception as e:
            messagebox.showerror("Restore Error", str(e))

    def save_settings(self) -> None:
        """Save settings changes (placeholder for future expansion)."""
        messagebox.showinfo("Settings", "Settings are saved via .env file.")

    def get_service_readiness(self) -> str:
        """Get formatted service readiness for display."""
        from src.gui.service_guard import get_service_status_text

        return get_service_status_text()

    def _rerun_setup(self) -> None:
        """Prompt to re-run the setup wizard."""
        messagebox.showinfo(
            "Setup Wizard",
            "To re-run the setup wizard, restart the application with:\n\n"
            "  python ironlung3.py --setup",
        )

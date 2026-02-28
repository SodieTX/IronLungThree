"""Settings tab - Credential management, service status, backup/recovery.

Provides a GUI for entering API keys and credentials so the user
never has to manually edit the .env file. Credentials are saved to
~/.ironlung/.env (kept out of the repo) and the config/service
registry are reloaded in-place.
"""

import re
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from src.core.logging import get_logger
from src.gui.tabs import TabBase
from src.gui.theme import COLORS

logger = get_logger(__name__)

# Where we persist credentials — inside the user-data directory,
# NOT in the repo checkout (which is .gitignored anyway).
_ENV_PATH = Path.home() / ".ironlung" / ".env"


def _read_env(path: Path) -> dict[str, str]:
    """Read key=value pairs from an .env file."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                if key:
                    values[key] = value
    return values


def _write_env(path: Path, values: dict[str, str]) -> None:
    """Write key=value pairs to an .env file, preserving comments.

    Uses secure file permissions (0600) to protect credentials.
    """
    from src.core.security import secure_mkdir, secure_write_file

    secure_mkdir(path.parent)

    # Read existing lines to preserve comments and ordering
    existing_lines: list[str] = []
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            existing_lines = f.readlines()

    # Track which keys we've already written (via update of existing lines)
    written_keys: set[str] = set()
    new_lines: list[str] = []

    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.partition("=")[0].strip()
            if key in values:
                # Update this line with the new value
                val = values[key]
                new_lines.append(f"{key}={val}\n")
                written_keys.add(key)
                continue
        new_lines.append(line)

    # Append any keys that weren't already in the file
    for key, val in values.items():
        if key not in written_keys and val:
            new_lines.append(f"{key}={val}\n")

    content = "".join(new_lines)
    secure_write_file(path, content)


# Credential field definitions: (env_key, label, is_secret)
_OUTLOOK_FIELDS = [
    ("OUTLOOK_CLIENT_ID", "Client ID", False),
    ("OUTLOOK_CLIENT_SECRET", "Client Secret", True),
    ("OUTLOOK_TENANT_ID", "Tenant ID", False),
    ("OUTLOOK_USER_EMAIL", "Email Address", False),
]

_CLAUDE_FIELDS = [
    ("CLAUDE_API_KEY", "API Key", True),
]

_ACTIVECAMPAIGN_FIELDS = [
    ("ACTIVECAMPAIGN_API_KEY", "API Key", True),
    ("ACTIVECAMPAIGN_URL", "API URL", False),
]

_GOOGLE_FIELDS = [
    ("GOOGLE_API_KEY", "API Key", True),
    ("GOOGLE_CX", "Search Engine ID", False),
]

_TRELLO_FIELDS = [
    ("TRELLO_API_KEY", "API Key", True),
    ("TRELLO_TOKEN", "Token", True),
    ("TRELLO_BOARD_ID", "Board ID or URL", False),
]


class SettingsTab(TabBase):
    """Application settings with credential entry, service status, and backups."""

    def __init__(self, parent: tk.Widget, db: object):
        super().__init__(parent, db)
        self._entries: dict[str, tk.StringVar] = {}
        self._show_vars: dict[str, tk.BooleanVar] = {}
        self._status_text: Optional[tk.Text] = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the full settings interface."""
        # Outer scrollable canvas
        canvas = tk.Canvas(self.parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.parent, orient="vertical", command=canvas.yview)
        self._scroll_frame = ttk.Frame(canvas)

        self._scroll_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable mouse-wheel scrolling
        def _on_mousewheel(event: tk.Event) -> None:  # type: ignore[type-arg]
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        # Linux scroll events
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        container = self._scroll_frame

        # --- System Readiness ---
        self._readiness_frame = ttk.LabelFrame(container, text="System Readiness", padding=12)
        self._readiness_frame.pack(fill="x", padx=12, pady=(12, 4))

        # Database status row
        db_row = ttk.Frame(self._readiness_frame)
        db_row.pack(fill="x", pady=4)

        self._db_status_label = ttk.Label(
            db_row,
            text="Checking database...",
            font=("Segoe UI", 10),
        )
        self._db_status_label.pack(side="left", padx=(0, 12))

        self._import_now_btn = ttk.Button(
            db_row,
            text="Import Contacts Now",
            command=self._go_to_import,
        )
        self._import_now_btn.pack(side="left")

        # Service readiness summary
        self._readiness_summary = ttk.Label(
            self._readiness_frame,
            text="",
            font=("Segoe UI", 10),
            wraplength=650,
        )
        self._readiness_summary.pack(fill="x", pady=(4, 0))

        # Populate on build
        self._refresh_readiness()

        # Title
        ttk.Label(container, text="Settings", font=("Segoe UI", 16, "bold")).pack(
            anchor="w", padx=12, pady=(12, 4)
        )

        ttk.Label(
            container,
            text="Enter your API credentials below. They are saved locally and never sent to this app's repository.",
            wraplength=700,
        ).pack(anchor="w", padx=12, pady=(0, 8))

        # --- Credential sections ---
        self._build_section(
            container,
            "Microsoft Outlook (Azure)",
            _OUTLOOK_FIELDS,
            hint="Azure Portal > App registrations > your app",
        )
        self._build_section(
            container,
            "Claude AI (Anthropic)",
            _CLAUDE_FIELDS,
            hint="console.anthropic.com > API Keys",
        )
        self._build_section(
            container,
            "ActiveCampaign",
            _ACTIVECAMPAIGN_FIELDS,
            hint="Settings > Developer in your AC account",
        )
        self._build_section(
            container,
            "Google Custom Search",
            _GOOGLE_FIELDS,
            hint="console.cloud.google.com > Credentials",
        )
        self._build_section(
            container,
            "Trello",
            _TRELLO_FIELDS,
            hint="trello.com/power-ups/admin > API Key, then generate a Token",
        )

        # --- Feature flags ---
        sep = ttk.Separator(container, orient="horizontal")
        sep.pack(fill="x", padx=12, pady=8)
        ttk.Label(container, text="Feature Flags", font=("Segoe UI", 12, "bold")).pack(
            anchor="w", padx=12, pady=4
        )

        flags_frame = ttk.Frame(container)
        flags_frame.pack(fill="x", padx=24, pady=4)

        self._debug_var = tk.BooleanVar(value=False)
        self._dryrun_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(flags_frame, text="Debug mode", variable=self._debug_var).pack(
            anchor="w", pady=2
        )
        ttk.Checkbutton(
            flags_frame, text="Dry-run mode (emails logged, not sent)", variable=self._dryrun_var
        ).pack(anchor="w", pady=2)

        # --- Save button ---
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x", padx=12, pady=(12, 4))
        self._save_btn = ttk.Button(btn_frame, text="Save Credentials", command=self._on_save)
        self._save_btn.pack(side="left")

        self._save_status = ttk.Label(btn_frame, text="")
        self._save_status.pack(side="left", padx=12)

        # --- Service status ---
        sep2 = ttk.Separator(container, orient="horizontal")
        sep2.pack(fill="x", padx=12, pady=8)
        ttk.Label(container, text="Service Status", font=("Segoe UI", 12, "bold")).pack(
            anchor="w", padx=12, pady=4
        )

        self._status_text = tk.Text(
            container, height=12, wrap="word", state="disabled", font=("Consolas", 10)
        )
        self._status_text.pack(fill="x", padx=12, pady=4)

        # --- Backup / Restore ---
        sep3 = ttk.Separator(container, orient="horizontal")
        sep3.pack(fill="x", padx=12, pady=8)
        ttk.Label(container, text="Database", font=("Segoe UI", 12, "bold")).pack(
            anchor="w", padx=12, pady=4
        )

        db_frame = ttk.Frame(container)
        db_frame.pack(fill="x", padx=12, pady=4)
        ttk.Button(db_frame, text="Create Backup", command=self.create_backup).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(db_frame, text="Restore Backup", command=self.restore_backup).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(db_frame, text="Reset & Re-seed Database", command=self._reset_and_reseed).pack(
            side="left"
        )

        # --- Update Application ---
        sep4 = ttk.Separator(container, orient="horizontal")
        sep4.pack(fill="x", padx=12, pady=8)
        ttk.Label(container, text="Update Application", font=("Segoe UI", 12, "bold")).pack(
            anchor="w", padx=12, pady=4
        )
        ttk.Label(
            container,
            text="Pull the latest version from GitHub. Your database and credentials are preserved.",
            foreground="#6c757d",
            wraplength=650,
        ).pack(anchor="w", padx=24, pady=(0, 4))

        update_frame = ttk.Frame(container)
        update_frame.pack(fill="x", padx=12, pady=4)
        self._update_btn = ttk.Button(
            update_frame, text="Update Now", command=self._update_application
        )
        self._update_btn.pack(side="left", padx=(0, 8))
        self._update_status_label = ttk.Label(update_frame, text="", font=("Segoe UI", 10))
        self._update_status_label.pack(side="left")

        self._update_log = tk.Text(
            container, height=6, wrap="word", state="disabled", font=("Consolas", 9)
        )
        self._update_log.pack(fill="x", padx=12, pady=(4, 0))

        # .env file path info
        ttk.Label(
            container,
            text=f"Credentials file: {_ENV_PATH}",
            font=("Consolas", 9),
            foreground="#6c757d",
        ).pack(anchor="w", padx=12, pady=(12, 12))

        # Load existing values into the fields
        self._load_current_values()

    def _build_section(
        self,
        parent: tk.Widget,
        title: str,
        fields: list[tuple[str, str, bool]],
        hint: str = "",
    ) -> None:
        """Build a labeled credential section with entry fields."""
        sep = ttk.Separator(parent, orient="horizontal")
        sep.pack(fill="x", padx=12, pady=8)

        ttk.Label(parent, text=title, font=("Segoe UI", 12, "bold")).pack(
            anchor="w", padx=12, pady=4
        )
        if hint:
            ttk.Label(parent, text=hint, foreground="#6c757d").pack(
                anchor="w", padx=24, pady=(0, 4)
            )

        for env_key, label, is_secret in fields:
            row = ttk.Frame(parent)
            row.pack(fill="x", padx=24, pady=2)

            ttk.Label(row, text=label, width=18, anchor="w").pack(side="left")

            var = tk.StringVar()
            self._entries[env_key] = var

            if is_secret:
                entry = ttk.Entry(row, textvariable=var, width=50, show="*")
                entry.pack(side="left", padx=(0, 4))

                # Toggle visibility
                show_var = tk.BooleanVar(value=False)
                self._show_vars[env_key] = show_var

                def _toggle(e=entry, sv=show_var) -> None:
                    e.configure(show="" if sv.get() else "*")

                ttk.Checkbutton(row, text="Show", variable=show_var, command=_toggle).pack(
                    side="left"
                )
            else:
                entry = ttk.Entry(row, textvariable=var, width=50)
                entry.pack(side="left")

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def _load_current_values(self) -> None:
        """Populate fields from the existing .env file."""
        # Read from the persistent location
        env_values = _read_env(_ENV_PATH)

        # Also check the repo-local .env (user may have started there)
        repo_env = Path.cwd() / ".env"
        if repo_env.exists():
            repo_values = _read_env(repo_env)
            # Persistent location takes priority
            for k, v in repo_values.items():
                if k not in env_values:
                    env_values[k] = v

        for env_key, var in self._entries.items():
            val = env_values.get(env_key, "")
            var.set(val)

        # Feature flags
        self._debug_var.set(env_values.get("IRONLUNG_DEBUG", "").lower() in ("true", "1", "yes"))
        self._dryrun_var.set(env_values.get("IRONLUNG_DRY_RUN", "").lower() in ("true", "1", "yes"))

    def _on_save(self) -> None:
        """Save credentials to .env and reload config."""
        values: dict[str, str] = {}
        for env_key, var in self._entries.items():
            val = var.get().strip()
            if val:
                values[env_key] = val

        # Feature flags
        values["IRONLUNG_DEBUG"] = "true" if self._debug_var.get() else "false"
        values["IRONLUNG_DRY_RUN"] = "true" if self._dryrun_var.get() else "false"

        try:
            _write_env(_ENV_PATH, values)
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            messagebox.showerror("Save Failed", f"Could not write credentials file:\n{e}")
            return

        # Security: credentials are ONLY written to the persistent user-data
        # location (~/.ironlung/.env), never to the repo checkout directory.
        # This prevents accidental commits of secrets to version control.

        # Reload config and service registry so changes take effect immediately
        from src.core.config import reset_config
        from src.core.services import reset_service_registry

        reset_config()
        reset_service_registry()

        self._refresh_status()
        self._save_status.config(text="Saved!", foreground="#28a745")

        # Clear the "Saved!" message after a few seconds
        self.parent.after(3000, lambda: self._save_status.config(text=""))

        logger.info("Credentials saved to persistent store")
        self._refresh_readiness()

    # ------------------------------------------------------------------
    # Service status
    # ------------------------------------------------------------------

    def _refresh_status(self) -> None:
        """Update the service status display."""
        if self._status_text is None:
            return
        from src.gui.service_guard import get_service_status_text

        status = get_service_status_text()
        self._status_text.config(state="normal")
        self._status_text.delete("1.0", tk.END)
        self._status_text.insert("1.0", status)
        self._status_text.config(state="disabled")

    # ------------------------------------------------------------------
    # TabBase interface
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload settings tab state."""
        self._load_current_values()
        self._refresh_readiness()
        self._refresh_status()
        logger.info("Settings tab refreshed")

    def on_activate(self) -> None:
        """Called when this tab becomes visible."""
        self.refresh()

    # ------------------------------------------------------------------
    # Backup / Restore
    # ------------------------------------------------------------------

    def create_backup(self) -> None:
        """Trigger manual backup."""
        from src.db.backup import BackupManager

        try:
            manager = BackupManager()
            path = manager.create_backup(label="manual")
            messagebox.showinfo("Backup Created", f"Backup saved to:\n{path}")
            logger.info(f"Manual backup created: {path}")
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            messagebox.showerror("Backup Failed", str(e))

    def restore_backup(self) -> None:
        """Open restore dialog."""
        file_path = filedialog.askopenfilename(
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        from src.db.backup import BackupManager

        try:
            manager = BackupManager()
            manager.restore_backup(Path(file_path))
            messagebox.showinfo("Restore Complete", f"Restored from:\n{file_path}")
            logger.info(f"Backup restored from {file_path}")
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            messagebox.showerror("Restore Failed", str(e))

    def save_settings(self) -> None:
        """Save settings changes (called externally)."""
        self._on_save()

    def _refresh_readiness(self) -> None:
        """Update the system readiness dashboard."""
        # Database status
        try:
            from src.db.models import Population

            pop_counts = self.db.get_population_counts()
            total = sum(pop_counts.values())
        except Exception:
            total = 0
            pop_counts = {}

        if total == 0:
            self._db_status_label.config(
                text="🔴  Database is empty — no prospects loaded",
                foreground=COLORS["danger"],
            )
            self._import_now_btn.pack(side="left")  # ensure visible
        else:
            unengaged = pop_counts.get(Population.UNENGAGED, 0)
            engaged = pop_counts.get(Population.ENGAGED, 0)
            self._db_status_label.config(
                text=f"🟢  {total} prospects loaded  ({unengaged} unengaged, {engaged} engaged)",
                foreground=COLORS["success"],
            )
            self._import_now_btn.pack_forget()  # hide — not needed

        # Service readiness
        try:
            from src.core.services import get_service_registry

            registry = get_service_registry()
            report = registry.readiness_report()

            lines = []
            for svc in report.services:
                if svc.configured:
                    lines.append(f"🟢 {svc.name}")
                elif svc.credentials_present:
                    lines.append(
                        f"🟡 {svc.name} (partial — missing {', '.join(svc.credentials_missing)})"
                    )
                else:
                    lines.append(f"⚪ {svc.name} (not configured)")
            self._readiness_summary.config(text="  |  ".join(lines))
        except Exception as e:
            logger.warning(f"Failed to check service readiness: {e}")
            self._readiness_summary.config(text="Could not check service status")

    def _reset_and_reseed(self) -> None:
        """Delete and re-create the database, then re-seed with sample data."""
        if not messagebox.askyesno(
            "Reset Database",
            "This will DELETE all current data and re-load from sample contacts.\n\n"
            "Are you sure? (A backup will be created first.)",
        ):
            return

        try:
            # Create backup first
            from src.db.backup import BackupManager

            try:
                backup_mgr = BackupManager()
                backup_path = backup_mgr.create_backup(label="pre_reset")
                logger.info(f"Pre-reset backup created: {backup_path}")
            except Exception as be:
                logger.warning(f"Pre-reset backup failed (continuing anyway): {be}")

            # Close and delete the database
            from src.core.config import get_config

            config = get_config()
            db_path = Path(str(config.db_path))

            self.db.close()

            if db_path.exists():
                db_path.unlink()
                logger.info(f"Deleted database: {db_path}")

            # Also remove WAL/SHM files if present
            for suffix in (".db-wal", ".db-shm"):
                wal_path = db_path.with_suffix(suffix)
                if wal_path.exists():
                    wal_path.unlink()

            # Re-initialize
            from src.db.database import Database

            new_db = Database()
            new_db.initialize()

            # Re-seed
            sample_csv = Path(__file__).parents[2] / "data" / "sample_contacts.csv"
            if not sample_csv.exists():
                # Try relative to the repo root
                import ironlung3

                sample_csv = Path(ironlung3.__file__).parent / "data" / "sample_contacts.csv"

            if sample_csv.exists():
                from src.db.intake import IntakeFunnel
                from src.integrations.csv_importer import CSVImporter

                importer = CSVImporter()
                mapping = {
                    "first_name": "First Name",
                    "last_name": "Last Name",
                    "email": "Email",
                    "phone": "Phone",
                    "company_name": "Company",
                    "title": "Title",
                    "state": "State",
                }
                records = importer.apply_mapping(sample_csv, mapping)
                funnel = IntakeFunnel(new_db)
                preview = funnel.analyze(
                    records, source_name="sample_data", filename="sample_contacts.csv"
                )
                result = funnel.commit(preview)

                try:
                    from src.engine.scoring import rescore_all

                    rescore_all(new_db)
                except Exception:
                    pass

                messagebox.showinfo(
                    "Reset Complete",
                    f"Database reset and re-seeded with {result.imported_count} contacts.\n\n"
                    "Restart the app for all tabs to refresh properly.",
                )
                logger.info(f"Database reset — seeded {result.imported_count} contacts")
            else:
                messagebox.showwarning(
                    "Reset Complete (No Seed Data)",
                    "Database was reset but sample_contacts.csv was not found.\n\n"
                    "Use the Import tab to load your own data.",
                )

            # Point the app's db reference to the new connection
            # (tabs will still reference the old one until restart,
            # but at least new tab activations will work)
            self.db = new_db
            if self.app:
                self.app.db = new_db

            self._refresh_readiness()

        except Exception as e:
            logger.error(f"Database reset failed: {e}", exc_info=True)
            messagebox.showerror("Reset Failed", f"Could not reset database:\n{e}")

    def _go_to_import(self) -> None:
        """Switch to the Import tab."""
        if self.app:
            self.app.switch_to_tab("Import")

    # ------------------------------------------------------------------
    # Application update
    # ------------------------------------------------------------------

    _GITHUB_URL = "https://github.com/SodieTX/IronLungThree.git"
    _SANDBOX_PROXY_RE = re.compile(
        r"https?://[^@]*@127\.0\.0\.1:\d+/git/(.+)",
    )

    def _append_update_log(self, text: str) -> None:
        """Append a line to the update log (must be called from the main thread)."""
        self._update_log.config(state="normal")
        self._update_log.insert(tk.END, text + "\n")
        self._update_log.see(tk.END)
        self._update_log.config(state="disabled")

    def _update_application(self) -> None:
        """Pull the latest code from GitHub, fixing sandbox proxies if needed."""
        self._update_btn.config(state="disabled")
        self._update_status_label.config(text="Updating...", foreground="#007bff")

        # Clear previous log
        self._update_log.config(state="normal")
        self._update_log.delete("1.0", tk.END)
        self._update_log.config(state="disabled")

        # Run git operations in a background thread so the GUI stays responsive
        thread = threading.Thread(target=self._do_update, daemon=True)
        thread.start()

    def _do_update(self) -> None:
        """Background worker: fix remote, pull, and report results."""
        repo_root = Path(__file__).resolve().parents[3]  # src/gui/tabs -> repo root
        log_lines: list[str] = []
        errors: list[str] = []

        def log(msg: str) -> None:
            log_lines.append(msg)
            self.parent.after(0, self._append_update_log, msg)

        def run_git(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["git", *args],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=60,
            )

        try:
            # 1. Check the current remote URL and fix sandbox proxies
            result = run_git("remote", "get-url", "origin")
            current_url = result.stdout.strip()
            log(f"Current remote: {current_url}")

            if self._SANDBOX_PROXY_RE.match(current_url):
                log("Detected sandbox proxy — resetting to GitHub...")
                fix = run_git("remote", "set-url", "origin", self._GITHUB_URL)
                if fix.returncode != 0:
                    errors.append(f"Failed to fix remote: {fix.stderr.strip()}")
                    log(f"ERROR: {fix.stderr.strip()}")
                else:
                    log(f"Remote set to {self._GITHUB_URL}")
            elif "github.com" not in current_url:
                # Unknown remote — set to the canonical GitHub URL
                log("Remote doesn't point to GitHub — resetting...")
                run_git("remote", "set-url", "origin", self._GITHUB_URL)
                log(f"Remote set to {self._GITHUB_URL}")
            else:
                log("Remote OK")

            # 2. Fetch latest from origin
            log("Fetching latest from origin...")
            fetch = run_git("fetch", "origin", "main")
            if fetch.returncode != 0:
                errors.append(f"Fetch failed: {fetch.stderr.strip()}")
                log(f"ERROR: {fetch.stderr.strip()}")
            else:
                log("Fetch complete")

            if not errors:
                # 3. Show what's incoming
                incoming = run_git("log", "HEAD..origin/main", "--oneline")
                commits = incoming.stdout.strip()
                if not commits:
                    log("Already up to date!")
                else:
                    count = len(commits.splitlines())
                    log(f"{count} new commit(s) available:")
                    for line in commits.splitlines()[:10]:
                        log(f"  {line}")
                    if count > 10:
                        log(f"  ... and {count - 10} more")

                    # 4. Pull (fast-forward preferred, fallback to rebase)
                    log("Pulling updates...")
                    pull = run_git("pull", "--ff-only", "origin", "main")
                    if pull.returncode != 0:
                        # Try rebase if ff-only fails (local commits exist)
                        log("Fast-forward not possible, trying rebase...")
                        pull = run_git("pull", "--rebase", "origin", "main")

                    if pull.returncode != 0:
                        errors.append(f"Pull failed: {pull.stderr.strip()}")
                        log(f"ERROR: {pull.stderr.strip()}")
                    else:
                        log("Pull complete — code is up to date!")

        except subprocess.TimeoutExpired:
            errors.append("Git command timed out (60s)")
            log("ERROR: Git command timed out")
        except FileNotFoundError:
            errors.append("Git is not installed or not on PATH")
            log("ERROR: Git is not installed or not on PATH")
        except Exception as e:
            errors.append(str(e))
            log(f"ERROR: {e}")

        # Report results back on the main thread
        if errors:
            logger.error(f"Application update failed: {errors}")
            self.parent.after(
                0,
                lambda: self._finish_update(False, "; ".join(errors)),
            )
        else:
            logger.info("Application updated successfully")
            self.parent.after(
                0,
                lambda: self._finish_update(True, ""),
            )

    def _finish_update(self, success: bool, error_msg: str) -> None:
        """Called on the main thread when the update finishes."""
        self._update_btn.config(state="normal")
        if success:
            self._update_status_label.config(
                text="Up to date! Restart the app to load new code.",
                foreground="#28a745",
            )
        else:
            self._update_status_label.config(
                text=f"Update failed: {error_msg}",
                foreground="#dc3545",
            )

"""Settings tab - Credential management, service status, backup/recovery.

Provides a GUI for entering API keys and credentials so the user
never has to manually edit the .env file. Credentials are saved to
~/.ironlung/.env (kept out of the repo) and the config/service
registry are reloaded in-place.
"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from src.core.logging import get_logger
from src.gui.tabs import TabBase

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
    """Write key=value pairs to an .env file, preserving comments."""
    path.parent.mkdir(parents=True, exist_ok=True)

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

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


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
        ttk.Button(db_frame, text="Restore Backup", command=self.restore_backup).pack(side="left")

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

        # Also write to the repo-local .env so the existing config loader picks it up
        try:
            repo_env = Path.cwd() / ".env"
            _write_env(repo_env, values)
        except Exception:
            pass  # Non-fatal; the persistent copy is the important one

        # Reload config and service registry so changes take effect immediately
        from src.core.config import reset_config
        from src.core.services import reset_service_registry

        reset_config()
        reset_service_registry()

        self._refresh_status()
        self._save_status.config(text="Saved!", foreground="#28a745")

        # Clear the "Saved!" message after a few seconds
        self.parent.after(3000, lambda: self._save_status.config(text=""))

        logger.info(f"Credentials saved to {_ENV_PATH}")

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
        """Reload settings state."""
        self._load_current_values()
        self._refresh_status()
        logger.info("Settings tab refreshed")

    def on_activate(self) -> None:
        """Called when this tab becomes visible."""
        self._refresh_status()

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

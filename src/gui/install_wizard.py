"""Install wizard — tkinter multi-step first-run setup.

Walks the user through initial configuration:
  Step 1: Welcome + name
  Step 2: Data paths (database, backups)
  Step 3: Integration credentials (Outlook, Claude API key)
  Step 4: Preferences (sounds, dry-run mode)
  Step 5: Review + finish

Backed by SetupWizard for persistence and Config for env-file generation.
"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable, Optional

from src.core.config import (
    DEFAULT_BACKUP_PATH,
    DEFAULT_DB_PATH,
    DEFAULT_LOG_PATH,
)
from src.core.logging import get_logger
from src.core.setup_wizard import SetupWizard

logger = get_logger(__name__)

# Number of wizard steps (0-indexed internally)
_NUM_STEPS = 5

# Styling constants
_PAD = 16
_FIELD_WIDTH = 48
_WINDOW_WIDTH = 620
_WINDOW_HEIGHT = 520
_BG = "#f5f5f5"
_FG = "#333333"
_ACCENT = "#0066cc"
_MUTED = "#6c757d"
_SUCCESS = "#28a745"
_FONT = ("Segoe UI", 10)
_FONT_LARGE = ("Segoe UI", 14, "bold")
_FONT_HEADING = ("Segoe UI", 12, "bold")
_FONT_SMALL = ("Segoe UI", 9)


class InstallWizard:
    """Multi-step tkinter install wizard for first-run setup.

    Usage:
        wizard = InstallWizard(data_dir=Path("data"))
        result = wizard.run()  # blocks until wizard closes
        # result is the SetupConfig if completed, None if cancelled
    """

    def __init__(self, data_dir: Path):
        self._setup = SetupWizard(data_dir=data_dir)
        self._result: Optional[object] = None
        self._current_step = 0

        # Tk variables — created in _build()
        self._root: Optional[tk.Tk] = None
        self._var_name: Optional[tk.StringVar] = None
        self._var_db_path: Optional[tk.StringVar] = None
        self._var_backup_dir: Optional[tk.StringVar] = None
        self._var_log_dir: Optional[tk.StringVar] = None
        self._var_outlook_client_id: Optional[tk.StringVar] = None
        self._var_outlook_client_secret: Optional[tk.StringVar] = None
        self._var_outlook_tenant_id: Optional[tk.StringVar] = None
        self._var_outlook_email: Optional[tk.StringVar] = None
        self._var_claude_api_key: Optional[tk.StringVar] = None
        self._var_sounds: Optional[tk.BooleanVar] = None
        self._var_dry_run: Optional[tk.BooleanVar] = None

        # Navigation buttons
        self._btn_back: Optional[ttk.Button] = None
        self._btn_next: Optional[ttk.Button] = None
        self._btn_cancel: Optional[ttk.Button] = None

        # Content frame swapped per step
        self._content_frame: Optional[ttk.Frame] = None

        # Step indicator labels
        self._step_labels: list[tk.Label] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> Optional[object]:
        """Run the wizard. Blocks until complete or cancelled.

        Returns:
            SetupConfig if completed, None if cancelled.
        """
        self._build()
        assert self._root is not None
        self._show_step(0)
        self._root.mainloop()
        return self._result

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Construct the wizard window."""
        root = tk.Tk()
        root.title("IronLung 3 — Setup Wizard")
        root.geometry(f"{_WINDOW_WIDTH}x{_WINDOW_HEIGHT}")
        root.resizable(False, False)
        root.configure(bg=_BG)
        root.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self._root = root

        # Initialize tk variables
        self._var_name = tk.StringVar(root, value="")
        self._var_db_path = tk.StringVar(root, value=str(DEFAULT_DB_PATH))
        self._var_backup_dir = tk.StringVar(root, value=str(DEFAULT_BACKUP_PATH))
        self._var_log_dir = tk.StringVar(root, value=str(DEFAULT_LOG_PATH))
        self._var_outlook_client_id = tk.StringVar(root, value="")
        self._var_outlook_client_secret = tk.StringVar(root, value="")
        self._var_outlook_tenant_id = tk.StringVar(root, value="")
        self._var_outlook_email = tk.StringVar(root, value="")
        self._var_claude_api_key = tk.StringVar(root, value="")
        self._var_sounds = tk.BooleanVar(root, value=True)
        self._var_dry_run = tk.BooleanVar(root, value=False)

        # --- Header ---
        header = tk.Frame(root, bg=_ACCENT, height=56)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header,
            text="IronLung 3 Setup",
            font=_FONT_LARGE,
            bg=_ACCENT,
            fg="white",
        ).pack(side=tk.LEFT, padx=_PAD, pady=10)

        # --- Step indicator ---
        step_bar = tk.Frame(root, bg=_BG)
        step_bar.pack(fill=tk.X, padx=_PAD, pady=(12, 4))
        step_names = ["Welcome", "Paths", "Integrations", "Preferences", "Review"]
        self._step_labels = []
        for i, name in enumerate(step_names):
            lbl = tk.Label(
                step_bar,
                text=f" {i + 1}. {name} ",
                font=_FONT_SMALL,
                bg=_BG,
                fg=_MUTED,
            )
            lbl.pack(side=tk.LEFT, padx=(0, 8))
            self._step_labels.append(lbl)

        # --- Separator ---
        ttk.Separator(root, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=_PAD, pady=(4, 0))

        # --- Content area ---
        self._content_frame = ttk.Frame(root)
        self._content_frame.pack(fill=tk.BOTH, expand=True, padx=_PAD, pady=_PAD)

        # --- Navigation bar ---
        ttk.Separator(root, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=_PAD)
        nav = ttk.Frame(root)
        nav.pack(fill=tk.X, padx=_PAD, pady=12)

        self._btn_cancel = ttk.Button(nav, text="Cancel", command=self._on_cancel)
        self._btn_cancel.pack(side=tk.LEFT)

        self._btn_next = ttk.Button(nav, text="Next →", command=self._on_next)
        self._btn_next.pack(side=tk.RIGHT)

        self._btn_back = ttk.Button(nav, text="← Back", command=self._on_back)
        self._btn_back.pack(side=tk.RIGHT, padx=(0, 8))

    # ------------------------------------------------------------------
    # Step rendering
    # ------------------------------------------------------------------

    def _show_step(self, step: int) -> None:
        """Render the given step in the content area."""
        self._current_step = step

        # Update step indicator
        for i, lbl in enumerate(self._step_labels):
            if i == step:
                lbl.configure(fg=_ACCENT, font=(*_FONT_SMALL[:2], "bold"))
            elif i < step:
                lbl.configure(fg=_SUCCESS, font=_FONT_SMALL)
            else:
                lbl.configure(fg=_MUTED, font=_FONT_SMALL)

        # Clear content frame
        assert self._content_frame is not None
        for child in self._content_frame.winfo_children():
            child.destroy()

        # Render step content
        builders = [
            self._build_step_welcome,
            self._build_step_paths,
            self._build_step_integrations,
            self._build_step_preferences,
            self._build_step_review,
        ]
        builders[step](self._content_frame)

        # Update navigation buttons
        assert self._btn_back is not None
        assert self._btn_next is not None
        self._btn_back.configure(state=tk.NORMAL if step > 0 else tk.DISABLED)
        if step == _NUM_STEPS - 1:
            self._btn_next.configure(text="Finish ✓")
        else:
            self._btn_next.configure(text="Next →")

    # --- Step 1: Welcome ---

    def _build_step_welcome(self, parent: ttk.Frame) -> None:
        tk.Label(
            parent,
            text="Welcome to IronLung 3",
            font=_FONT_HEADING,
            bg=_BG,
            fg=_FG,
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            parent,
            text="Let's get you set up. This will only take a minute.",
            font=_FONT,
            bg=_BG,
            fg=_MUTED,
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 16))

        tk.Label(
            parent,
            text="What's your first name?",
            font=_FONT,
            bg=_BG,
            fg=_FG,
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 4))
        assert self._var_name is not None
        name_entry = ttk.Entry(parent, textvariable=self._var_name, width=_FIELD_WIDTH)
        name_entry.pack(anchor=tk.W, pady=(0, 16))
        name_entry.focus_set()

        tk.Label(
            parent,
            text=(
                "IronLung 3 is an ADHD-optimized sales pipeline manager.\n"
                "It acts as your cognitive prosthetic — managing follow-ups,\n"
                "drafting emails, and keeping your pipeline breathing\n"
                "while you focus on selling."
            ),
            font=_FONT_SMALL,
            bg=_BG,
            fg=_MUTED,
            anchor=tk.W,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(8, 0))

    # --- Step 2: Paths ---

    def _build_step_paths(self, parent: ttk.Frame) -> None:
        tk.Label(
            parent,
            text="Data Locations",
            font=_FONT_HEADING,
            bg=_BG,
            fg=_FG,
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            parent,
            text="Where should IronLung store its data? Defaults work for most setups.",
            font=_FONT,
            bg=_BG,
            fg=_MUTED,
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 16))

        self._path_field(parent, "Database file:", self._var_db_path, is_file=True)
        self._path_field(parent, "Backup directory:", self._var_backup_dir, is_file=False)
        self._path_field(parent, "Log directory:", self._var_log_dir, is_file=False)

    # --- Step 3: Integrations ---

    def _build_step_integrations(self, parent: ttk.Frame) -> None:
        tk.Label(
            parent,
            text="Integrations (Optional)",
            font=_FONT_HEADING,
            bg=_BG,
            fg=_FG,
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            parent,
            text="Skip any of these — you can configure them later in .env.",
            font=_FONT,
            bg=_BG,
            fg=_MUTED,
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 12))

        # Scrollable frame for the integration fields
        canvas = tk.Canvas(parent, bg=_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Outlook section
        tk.Label(
            inner,
            text="Microsoft Outlook (email sending)",
            font=(*_FONT[:1], _FONT[1], "bold"),
            bg=_BG,
            fg=_FG,
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 4))
        self._text_field(inner, "Client ID:", self._var_outlook_client_id)
        self._text_field(inner, "Client Secret:", self._var_outlook_client_secret, show="*")
        self._text_field(inner, "Tenant ID:", self._var_outlook_tenant_id)
        self._text_field(inner, "Email address:", self._var_outlook_email)

        ttk.Separator(inner, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=12)

        # Claude section
        tk.Label(
            inner,
            text="Claude API (AI features)",
            font=(*_FONT[:1], _FONT[1], "bold"),
            bg=_BG,
            fg=_FG,
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 4))
        self._text_field(inner, "API Key:", self._var_claude_api_key, show="*")

    # --- Step 4: Preferences ---

    def _build_step_preferences(self, parent: ttk.Frame) -> None:
        tk.Label(
            parent,
            text="Preferences",
            font=_FONT_HEADING,
            bg=_BG,
            fg=_FG,
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            parent,
            text="Customize your experience.",
            font=_FONT,
            bg=_BG,
            fg=_MUTED,
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 16))

        assert self._var_sounds is not None
        ttk.Checkbutton(
            parent,
            text="Enable sounds (streaks, celebrations, alerts)",
            variable=self._var_sounds,
        ).pack(anchor=tk.W, pady=(0, 8))

        assert self._var_dry_run is not None
        ttk.Checkbutton(
            parent,
            text="Dry-run mode (emails logged but never sent)",
            variable=self._var_dry_run,
        ).pack(anchor=tk.W, pady=(0, 8))

        tk.Label(
            parent,
            text=(
                "You can change these anytime by editing the .env file\n"
                "or re-running the setup wizard."
            ),
            font=_FONT_SMALL,
            bg=_BG,
            fg=_MUTED,
            anchor=tk.W,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(16, 0))

    # --- Step 5: Review ---

    def _build_step_review(self, parent: ttk.Frame) -> None:
        tk.Label(
            parent,
            text="Review & Finish",
            font=_FONT_HEADING,
            bg=_BG,
            fg=_FG,
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            parent,
            text="Everything look right? Hit Finish to save and launch.",
            font=_FONT,
            bg=_BG,
            fg=_MUTED,
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 12))

        assert self._var_name is not None
        assert self._var_db_path is not None
        assert self._var_backup_dir is not None
        assert self._var_sounds is not None
        assert self._var_dry_run is not None
        assert self._var_outlook_client_id is not None
        assert self._var_claude_api_key is not None

        outlook_status = "Configured" if self._var_outlook_client_id.get().strip() else "Skipped"
        claude_status = "Configured" if self._var_claude_api_key.get().strip() else "Skipped"

        lines = [
            ("Name", self._var_name.get().strip() or "(not set)"),
            ("Database", self._var_db_path.get()),
            ("Backups", self._var_backup_dir.get()),
            ("Sounds", "On" if self._var_sounds.get() else "Off"),
            ("Dry-run", "On" if self._var_dry_run.get() else "Off"),
            ("Outlook", outlook_status),
            ("Claude AI", claude_status),
        ]

        for label, value in lines:
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, pady=2)
            tk.Label(
                row,
                text=f"{label}:",
                font=(*_FONT[:1], _FONT[1], "bold"),
                bg=_BG,
                fg=_FG,
                width=14,
                anchor=tk.W,
            ).pack(side=tk.LEFT)
            tk.Label(
                row,
                text=value,
                font=_FONT,
                bg=_BG,
                fg=_FG,
                anchor=tk.W,
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(
            parent,
            text="\nA .env file will be generated with your settings.",
            font=_FONT_SMALL,
            bg=_BG,
            fg=_MUTED,
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(8, 0))

    # ------------------------------------------------------------------
    # Widget helpers
    # ------------------------------------------------------------------

    def _path_field(
        self,
        parent: tk.Widget,
        label: str,
        var: Optional[tk.StringVar],
        is_file: bool = False,
    ) -> None:
        """Add a path entry with a Browse button."""
        tk.Label(parent, text=label, font=_FONT, bg=_BG, fg=_FG, anchor=tk.W).pack(
            fill=tk.X, pady=(0, 2)
        )
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(0, 10))
        assert var is not None
        ttk.Entry(row, textvariable=var, width=_FIELD_WIDTH).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(
            row,
            text="Browse…",
            command=lambda: self._browse(var, is_file),
        ).pack(side=tk.RIGHT, padx=(6, 0))

    def _text_field(
        self,
        parent: tk.Widget,
        label: str,
        var: Optional[tk.StringVar],
        show: str = "",
    ) -> None:
        """Add a labeled text entry."""
        tk.Label(parent, text=label, font=_FONT, bg=_BG, fg=_FG, anchor=tk.W).pack(
            fill=tk.X, pady=(0, 2)
        )
        assert var is not None
        ttk.Entry(parent, textvariable=var, width=_FIELD_WIDTH, show=show).pack(
            anchor=tk.W, pady=(0, 8)
        )

    def _browse(self, var: Optional[tk.StringVar], is_file: bool) -> None:
        """Open a file/directory picker and update the variable."""
        if var is None:
            return
        if is_file:
            path = filedialog.asksaveasfilename(
                title="Choose database location",
                defaultextension=".db",
                filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")],
            )
        else:
            path = filedialog.askdirectory(title="Choose directory")
        if path:
            var.set(path)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _on_next(self) -> None:
        """Advance to next step or finish."""
        if self._current_step < _NUM_STEPS - 1:
            self._show_step(self._current_step + 1)
        else:
            self._finish()

    def _on_back(self) -> None:
        """Go to previous step."""
        if self._current_step > 0:
            self._show_step(self._current_step - 1)

    def _on_cancel(self) -> None:
        """Cancel the wizard."""
        self._result = None
        assert self._root is not None
        self._root.destroy()

    # ------------------------------------------------------------------
    # Finish / persist
    # ------------------------------------------------------------------

    def _finish(self) -> None:
        """Collect values, persist config, write .env, and close."""
        assert self._var_name is not None
        assert self._var_db_path is not None
        assert self._var_backup_dir is not None
        assert self._var_sounds is not None

        # Persist to SetupWizard backend
        name = self._var_name.get().strip()
        self._setup.set_user_name(name)
        self._setup.set_db_path(self._var_db_path.get().strip())
        self._setup.set_backup_dir(self._var_backup_dir.get().strip())
        self._setup.set_sounds_enabled(self._var_sounds.get())

        has_outlook = bool(
            self._var_outlook_client_id
            and self._var_outlook_client_id.get().strip()
            and self._var_outlook_client_secret
            and self._var_outlook_client_secret.get().strip()
            and self._var_outlook_tenant_id
            and self._var_outlook_tenant_id.get().strip()
        )
        self._setup.set_outlook_configured(has_outlook)

        config = self._setup.complete_setup()
        self._result = config

        # Write .env file
        self._write_env_file()

        logger.info(
            "Install wizard completed",
            extra={"context": {"user_name": name}},
        )

        assert self._root is not None
        self._root.destroy()

    def _write_env_file(self) -> None:
        """Generate a .env file from wizard values."""
        assert self._var_db_path is not None
        assert self._var_backup_dir is not None
        assert self._var_log_dir is not None
        assert self._var_outlook_client_id is not None
        assert self._var_outlook_client_secret is not None
        assert self._var_outlook_tenant_id is not None
        assert self._var_outlook_email is not None
        assert self._var_claude_api_key is not None
        assert self._var_dry_run is not None
        assert self._var_sounds is not None

        env_path = Path.cwd() / ".env"
        if env_path.exists():
            logger.info(".env already exists, skipping write")
            return

        lines = [
            "# IronLung 3 — Generated by Install Wizard",
            "",
            "# Paths",
            f"IRONLUNG_DB_PATH={self._var_db_path.get()}",
            f"IRONLUNG_BACKUP_PATH={self._var_backup_dir.get()}",
            f"IRONLUNG_LOG_PATH={self._var_log_dir.get()}",
            "",
        ]

        # Outlook
        cid = self._var_outlook_client_id.get().strip()
        csec = self._var_outlook_client_secret.get().strip()
        tid = self._var_outlook_tenant_id.get().strip()
        email = self._var_outlook_email.get().strip()
        if cid or csec or tid or email:
            lines.append("# Microsoft Outlook")
            if cid:
                lines.append(f"OUTLOOK_CLIENT_ID={cid}")
            if csec:
                lines.append(f"OUTLOOK_CLIENT_SECRET={csec}")
            if tid:
                lines.append(f"OUTLOOK_TENANT_ID={tid}")
            if email:
                lines.append(f"OUTLOOK_USER_EMAIL={email}")
            lines.append("")

        # Claude
        api_key = self._var_claude_api_key.get().strip()
        if api_key:
            lines.append("# Claude AI")
            lines.append(f"CLAUDE_API_KEY={api_key}")
            lines.append("")

        # Feature flags
        lines.append("# Feature Flags")
        lines.append(f"IRONLUNG_DEBUG=false")
        lines.append(f"IRONLUNG_DRY_RUN={'true' if self._var_dry_run.get() else 'false'}")
        lines.append("")

        try:
            env_path.write_text("\n".join(lines), encoding="utf-8")
            logger.info("Generated .env file", extra={"context": {"path": str(env_path)}})
        except OSError:
            logger.warning("Failed to write .env file", exc_info=True)

    # ------------------------------------------------------------------
    # Accessors (for testing without mainloop)
    # ------------------------------------------------------------------

    @property
    def current_step(self) -> int:
        """Current step index (0-based)."""
        return self._current_step

    @property
    def setup_wizard(self) -> SetupWizard:
        """Access the underlying SetupWizard for inspection."""
        return self._setup

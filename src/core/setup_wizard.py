"""First-run setup wizard — captures initial configuration.

On first launch, the wizard collects:
- Database location (default: data/ironlung.db)
- Backup directory
- Outlook credentials (optional, can skip)
- Sound preferences (on/off)
- Name (for greeting)

State is tracked via a "setup_complete" flag in config.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SetupConfig:
    """Configuration gathered during first-run wizard."""

    user_name: str = ""
    db_path: str = "data/ironlung.db"
    backup_dir: str = "data/backups"
    sounds_enabled: bool = True
    outlook_configured: bool = False
    setup_complete: bool = False


class SetupWizard:
    """Manages first-run setup state.

    The wizard logic (what to ask, in what order) is here.
    The actual UI (tkinter dialogs) is wired in the app module.
    This separation allows testing the wizard flow without tkinter.
    """

    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._config_path = data_dir / "setup_config.json"
        self._config: SetupConfig = self._load()

    def is_setup_complete(self) -> bool:
        """Check if first-run setup has been completed."""
        return self._config.setup_complete

    def needs_setup(self) -> bool:
        """Check if setup is needed (inverse of is_setup_complete)."""
        return not self._config.setup_complete

    def get_config(self) -> SetupConfig:
        """Get the current setup configuration."""
        return self._config

    def set_user_name(self, name: str) -> None:
        """Set the user's name for greetings."""
        self._config.user_name = name.strip()

    def set_db_path(self, path: str) -> None:
        """Set the database file path."""
        self._config.db_path = path

    def set_backup_dir(self, path: str) -> None:
        """Set the backup directory."""
        self._config.backup_dir = path

    def set_sounds_enabled(self, enabled: bool) -> None:
        """Set sound preference."""
        self._config.sounds_enabled = enabled

    def set_outlook_configured(self, configured: bool) -> None:
        """Mark Outlook as configured (or skipped)."""
        self._config.outlook_configured = configured

    def complete_setup(self) -> SetupConfig:
        """Mark setup as complete and persist.

        Returns:
            The final SetupConfig
        """
        self._config.setup_complete = True
        self._save()
        logger.info(
            "Setup wizard completed",
            extra={
                "context": {
                    "user_name": self._config.user_name,
                    "sounds": self._config.sounds_enabled,
                    "outlook": self._config.outlook_configured,
                }
            },
        )
        return self._config

    def reset(self) -> None:
        """Reset setup state (for testing or re-configuration)."""
        self._config = SetupConfig()
        if self._config_path.exists():
            self._config_path.unlink()

    def _save(self) -> None:
        """Persist config to disk."""
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            self._config_path.write_text(
                json.dumps(asdict(self._config), indent=2),
                encoding="utf-8",
            )
        except OSError:
            logger.warning("Failed to save setup config", exc_info=True)

    def _load(self) -> SetupConfig:
        """Load config from disk."""
        if not self._config_path.exists():
            return SetupConfig()
        try:
            data = json.loads(self._config_path.read_text(encoding="utf-8"))
            return SetupConfig(**{k: v for k, v in data.items() if k in SetupConfig.__dataclass_fields__})
        except (OSError, json.JSONDecodeError, TypeError):
            logger.warning("Failed to load setup config, using defaults", exc_info=True)
            return SetupConfig()

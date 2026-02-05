"""Backup and restore system for IronLung 3.

Provides:
    - Timestamped local backups using SQLite backup API
    - Cloud sync to OneDrive
    - Backup retention cleanup
    - Safe restore with pre-restore backup

Usage:
    from src.db.backup import BackupManager

    backup = BackupManager()
    path = backup.create_backup(label="manual")
    backup.sync_to_cloud()
    backup.restore_backup(path)
"""

import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.config import get_config
from src.core.exceptions import DatabaseError
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BackupInfo:
    """Information about a backup file.

    Attributes:
        path: Full path to backup file
        label: Backup label (manual, nightly, pre_import, pre_restore)
        timestamp: When backup was created
        size_bytes: File size in bytes
    """

    path: Path
    label: str
    timestamp: datetime
    size_bytes: int


class BackupManager:
    """Manages database backups.

    Backup naming format: ironlung3_YYYYMMDD_HHMMSS_label.db

    Labels:
        - manual: User-triggered backup
        - nightly: Nightly cycle backup
        - pre_import: Before bulk import
        - pre_restore: Safety backup before restore
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        backup_path: Optional[Path] = None,
        cloud_sync_path: Optional[Path] = None,
    ):
        """Initialize backup manager.

        Args:
            db_path: Path to database file
            backup_path: Directory for backups
            cloud_sync_path: OneDrive sync directory (optional)
        """
        config = get_config()
        self.db_path = db_path or config.db_path
        self.backup_path = backup_path or config.backup_path
        self.cloud_sync_path = cloud_sync_path or config.cloud_sync_path

    def create_backup(self, label: str = "manual") -> Path:
        """Create a timestamped backup.

        Uses SQLite backup API for consistent backup.

        Args:
            label: Backup label for identification

        Returns:
            Path to created backup file

        Raises:
            DatabaseError: If backup fails
        """
        raise NotImplementedError("Phase 1, Step 1.11")

    def list_backups(self) -> list[BackupInfo]:
        """List all backups, newest first.

        Returns:
            List of BackupInfo objects
        """
        raise NotImplementedError("Phase 1, Step 1.11")

    def restore_backup(self, backup_path: Path) -> bool:
        """Restore database from backup.

        Creates a pre-restore safety backup first.

        Args:
            backup_path: Path to backup file to restore

        Returns:
            True if restore successful

        Raises:
            DatabaseError: If restore fails
        """
        raise NotImplementedError("Phase 1, Step 1.11")

    def cleanup_old_backups(self, keep_days: int = 30) -> int:
        """Remove backups older than keep_days.

        Args:
            keep_days: Number of days to keep backups

        Returns:
            Number of backups removed
        """
        raise NotImplementedError("Phase 1, Step 1.11")

    def sync_to_cloud(self) -> bool:
        """Copy latest backup to OneDrive sync folder.

        Returns:
            True if sync successful, False if no cloud path configured
        """
        raise NotImplementedError("Phase 1, Step 1.11")

    def _generate_backup_filename(self, label: str) -> str:
        """Generate backup filename with timestamp."""
        now = datetime.now()
        return f"ironlung3_{now.strftime('%Y%m%d_%H%M%S')}_{label}.db"

    def _parse_backup_filename(self, filename: str) -> Optional[tuple[datetime, str]]:
        """Parse timestamp and label from backup filename.

        Returns:
            Tuple of (timestamp, label) or None if invalid format
        """
        # Expected format: ironlung3_YYYYMMDD_HHMMSS_label.db
        try:
            parts = filename.replace(".db", "").split("_")
            if len(parts) >= 4 and parts[0] == "ironlung3":
                date_str = parts[1]
                time_str = parts[2]
                label = "_".join(parts[3:])
                timestamp = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                return (timestamp, label)
        except (ValueError, IndexError):
            pass
        return None

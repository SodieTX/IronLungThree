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
        try:
            self.backup_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(f"Cannot create backup directory: {e}")
            raise DatabaseError(f"Cannot create backup directory: {e}") from e

        filename = self._generate_backup_filename(label)
        dest = self.backup_path / filename

        try:
            # Use SQLite backup API for consistent snapshot
            with (
                sqlite3.connect(str(self.db_path)) as source_conn,
                sqlite3.connect(str(dest)) as dest_conn,
            ):
                source_conn.backup(dest_conn)

            logger.info(
                "Backup created",
                extra={"context": {"path": str(dest), "label": label}},
            )
            return dest
        except (sqlite3.Error, OSError) as e:
            # Clean up partial backup
            if dest.exists():
                dest.unlink()
            raise DatabaseError(f"Backup failed: {e}") from e

    def list_backups(self) -> list[BackupInfo]:
        """List all backups, newest first.

        Returns:
            List of BackupInfo objects
        """
        if not self.backup_path.exists():
            return []

        backups: list[BackupInfo] = []
        for f in self.backup_path.glob("ironlung3_*.db"):
            parsed = self._parse_backup_filename(f.name)
            if parsed:
                timestamp, label = parsed
                backups.append(
                    BackupInfo(
                        path=f,
                        label=label,
                        timestamp=timestamp,
                        size_bytes=f.stat().st_size,
                    )
                )

        # Sort newest first
        backups.sort(key=lambda b: b.timestamp, reverse=True)
        return backups

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
        backup_path = Path(backup_path)
        if not backup_path.exists():
            raise DatabaseError(f"Backup file not found: {backup_path}")

        # Validate the backup is a valid SQLite database
        try:
            with sqlite3.connect(str(backup_path)) as test_conn:
                test_conn.execute("SELECT count(*) FROM sqlite_master")
        except sqlite3.Error as e:
            raise DatabaseError(f"Backup file is corrupt: {e}") from e

        # Create pre-restore safety backup
        if Path(self.db_path).exists():
            try:
                self.create_backup(label="pre_restore")
            except DatabaseError:
                logger.warning("Could not create pre-restore safety backup")

        # Restore by copying backup over current database
        try:
            shutil.copy2(str(backup_path), str(self.db_path))
            logger.info(
                "Database restored",
                extra={"context": {"from": str(backup_path)}},
            )
            return True
        except OSError as e:
            raise DatabaseError(f"Restore failed: {e}") from e

    def cleanup_old_backups(self, keep_days: int = 30) -> int:
        """Remove backups older than keep_days.

        Args:
            keep_days: Number of days to keep backups

        Returns:
            Number of backups removed
        """
        if not self.backup_path.exists():
            return 0

        cutoff = datetime.now().timestamp() - (keep_days * 86400)
        removed = 0

        for backup in self.list_backups():
            if backup.timestamp.timestamp() < cutoff:
                try:
                    backup.path.unlink()
                    removed += 1
                except OSError:
                    logger.warning(f"Could not remove old backup: {backup.path}")

        if removed:
            logger.info(f"Cleaned up {removed} old backups")
        return removed

    def sync_to_cloud(self) -> bool:
        """Copy latest backup to OneDrive sync folder.

        Returns:
            True if sync successful, False if no cloud path configured
        """
        if not self.cloud_sync_path:
            return False

        if not self.cloud_sync_path.exists():
            logger.info(
                "Cloud sync directory missing",
                extra={"context": {"path": str(self.cloud_sync_path)}},
            )
            return False

        backups = self.list_backups()
        if not backups:
            return False

        latest = backups[0]
        try:
            dest = self.cloud_sync_path / latest.path.name
            shutil.copy2(str(latest.path), str(dest))
            logger.info("Backup synced to cloud", extra={"context": {"path": str(dest)}})
            return True
        except OSError as e:
            logger.warning(f"Cloud sync failed: {e}")
            return False

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

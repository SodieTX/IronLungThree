"""Tests for backup management."""

import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.core.exceptions import DatabaseError
from src.db.backup import BackupInfo, BackupManager

# =========================================================================
# BACKUP CREATION TESTS
# =========================================================================


class TestCreateBackup:
    """Test backup creation."""

    def test_create_backup_file(self, tmp_path: Path):
        """Creates a valid backup file."""
        db_path = tmp_path / "source.db"
        backup_dir = tmp_path / "backups"

        # Create a real SQLite database
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'hello')")
        conn.commit()
        conn.close()

        manager = BackupManager(db_path=db_path, backup_path=backup_dir)
        result_path = manager.create_backup(label="manual")

        assert result_path.exists()
        assert result_path.stat().st_size > 0
        assert "manual" in result_path.name
        assert result_path.name.startswith("ironlung3_")
        assert result_path.name.endswith(".db")

    def test_backup_is_valid_sqlite(self, tmp_path: Path):
        """Backup file is a valid SQLite database with data."""
        db_path = tmp_path / "source.db"
        backup_dir = tmp_path / "backups"

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'data')")
        conn.commit()
        conn.close()

        manager = BackupManager(db_path=db_path, backup_path=backup_dir)
        result_path = manager.create_backup()

        # Verify backup has the data
        backup_conn = sqlite3.connect(str(result_path))
        row = backup_conn.execute("SELECT val FROM test WHERE id = 1").fetchone()
        assert row[0] == "data"
        backup_conn.close()

    def test_backup_with_different_labels(self, tmp_path: Path):
        """Supports different label types."""
        db_path = tmp_path / "source.db"
        backup_dir = tmp_path / "backups"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        manager = BackupManager(db_path=db_path, backup_path=backup_dir)

        for label in ["manual", "nightly", "pre_import", "pre_restore"]:
            path = manager.create_backup(label=label)
            assert label in path.name

    def test_backup_creates_directory(self, tmp_path: Path):
        """Backup directory is created if it doesn't exist."""
        db_path = tmp_path / "source.db"
        backup_dir = tmp_path / "new" / "backup" / "dir"

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        manager = BackupManager(db_path=db_path, backup_path=backup_dir)
        path = manager.create_backup()
        assert path.exists()
        assert backup_dir.exists()


# =========================================================================
# LIST BACKUPS TESTS
# =========================================================================


class TestListBackups:
    """Test listing backups."""

    def test_list_empty(self, tmp_path: Path):
        """Returns empty list when no backups exist."""
        manager = BackupManager(
            db_path=tmp_path / "db.db",
            backup_path=tmp_path / "backups",
        )
        assert manager.list_backups() == []

    def test_list_returns_backups(self, tmp_path: Path):
        """Lists created backups."""
        db_path = tmp_path / "source.db"
        backup_dir = tmp_path / "backups"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        manager = BackupManager(db_path=db_path, backup_path=backup_dir)
        manager.create_backup(label="first")
        time.sleep(1.1)  # Ensure different timestamps
        manager.create_backup(label="second")

        backups = manager.list_backups()
        assert len(backups) == 2
        # Newest first
        assert backups[0].label == "second"
        assert backups[1].label == "first"

    def test_list_has_backup_info(self, tmp_path: Path):
        """BackupInfo has path, label, timestamp, size."""
        db_path = tmp_path / "source.db"
        backup_dir = tmp_path / "backups"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        manager = BackupManager(db_path=db_path, backup_path=backup_dir)
        manager.create_backup(label="test")

        backups = manager.list_backups()
        info = backups[0]
        assert isinstance(info, BackupInfo)
        assert isinstance(info.path, Path)
        assert info.label == "test"
        assert isinstance(info.timestamp, datetime)
        assert info.size_bytes > 0

    def test_list_ignores_non_backup_files(self, tmp_path: Path):
        """Non-backup files in directory are ignored."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        (backup_dir / "random_file.db").write_text("not a backup")
        (backup_dir / "notes.txt").write_text("some notes")

        manager = BackupManager(
            db_path=tmp_path / "db.db",
            backup_path=backup_dir,
        )
        assert manager.list_backups() == []


# =========================================================================
# RESTORE BACKUP TESTS
# =========================================================================


class TestRestoreBackup:
    """Test backup restoration."""

    def test_restore_overwrites_db(self, tmp_path: Path):
        """Restore replaces current database with backup data."""
        db_path = tmp_path / "live.db"
        backup_dir = tmp_path / "backups"

        # Create original database with data
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (val TEXT)")
        conn.execute("INSERT INTO test VALUES ('original')")
        conn.commit()
        conn.close()

        manager = BackupManager(db_path=db_path, backup_path=backup_dir)
        backup_path = manager.create_backup(label="before_change")

        # Modify the live database
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE test SET val = 'modified'")
        conn.commit()
        conn.close()

        # Restore from backup
        result = manager.restore_backup(backup_path)
        assert result is True

        # Verify original data is back
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT val FROM test").fetchone()
        assert row[0] == "original"
        conn.close()

    def test_restore_creates_pre_restore_backup(self, tmp_path: Path):
        """Restore creates a safety backup before overwriting."""
        db_path = tmp_path / "live.db"
        backup_dir = tmp_path / "backups"

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        manager = BackupManager(db_path=db_path, backup_path=backup_dir)
        backup_path = manager.create_backup(label="manual")

        # Restore triggers pre_restore backup
        manager.restore_backup(backup_path)

        backups = manager.list_backups()
        labels = [b.label for b in backups]
        assert "pre_restore" in labels

    def test_restore_nonexistent_file_raises(self, tmp_path: Path):
        """Raises DatabaseError for missing backup file."""
        manager = BackupManager(
            db_path=tmp_path / "db.db",
            backup_path=tmp_path / "backups",
        )
        with pytest.raises(DatabaseError, match="Backup file not found"):
            manager.restore_backup(tmp_path / "nonexistent.db")

    def test_restore_corrupt_file_raises(self, tmp_path: Path):
        """Raises DatabaseError for corrupt backup file."""
        corrupt_file = tmp_path / "corrupt.db"
        corrupt_file.write_text("this is not a sqlite database")

        manager = BackupManager(
            db_path=tmp_path / "db.db",
            backup_path=tmp_path / "backups",
        )
        with pytest.raises(DatabaseError, match="corrupt"):
            manager.restore_backup(corrupt_file)


# =========================================================================
# CLEANUP TESTS
# =========================================================================


class TestCleanupOldBackups:
    """Test old backup cleanup."""

    def test_cleanup_removes_old_backups(self, tmp_path: Path):
        """Removes backups older than keep_days."""
        db_path = tmp_path / "source.db"
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        manager = BackupManager(db_path=db_path, backup_path=backup_dir)

        # Create a backup with an old timestamp in the filename
        old_date = datetime.now() - timedelta(days=60)
        old_name = f"ironlung3_{old_date.strftime('%Y%m%d_%H%M%S')}_old.db"
        old_backup = backup_dir / old_name
        # Copy the source db to simulate a real backup
        import shutil

        shutil.copy2(str(db_path), str(old_backup))

        # Create a recent backup
        manager.create_backup(label="recent")

        removed = manager.cleanup_old_backups(keep_days=30)
        assert removed == 1

        remaining = manager.list_backups()
        assert len(remaining) == 1
        assert remaining[0].label == "recent"

    def test_cleanup_keeps_recent(self, tmp_path: Path):
        """Keeps backups newer than keep_days."""
        db_path = tmp_path / "source.db"
        backup_dir = tmp_path / "backups"

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        manager = BackupManager(db_path=db_path, backup_path=backup_dir)
        manager.create_backup(label="new")

        removed = manager.cleanup_old_backups(keep_days=30)
        assert removed == 0
        assert len(manager.list_backups()) == 1

    def test_cleanup_no_backups(self, tmp_path: Path):
        """Returns 0 when no backup directory exists."""
        manager = BackupManager(
            db_path=tmp_path / "db.db",
            backup_path=tmp_path / "nonexistent",
        )
        assert manager.cleanup_old_backups() == 0


# =========================================================================
# CLOUD SYNC TESTS
# =========================================================================


class TestCloudSync:
    """Test OneDrive cloud sync."""

    def test_sync_copies_latest(self, tmp_path: Path):
        """Syncs latest backup to cloud directory."""
        db_path = tmp_path / "source.db"
        backup_dir = tmp_path / "backups"
        cloud_dir = tmp_path / "onedrive"
        cloud_dir.mkdir()

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        manager = BackupManager(
            db_path=db_path,
            backup_path=backup_dir,
            cloud_sync_path=cloud_dir,
        )
        backup_path = manager.create_backup(label="sync_test")
        result = manager.sync_to_cloud()

        assert result is True
        synced_files = list(cloud_dir.glob("ironlung3_*.db"))
        assert len(synced_files) == 1

    def test_sync_no_cloud_path(self, tmp_path: Path):
        """Returns False when no cloud path configured."""
        manager = BackupManager(
            db_path=tmp_path / "db.db",
            backup_path=tmp_path / "backups",
            cloud_sync_path=None,
        )
        assert manager.sync_to_cloud() is False

    def test_sync_missing_cloud_dir(self, tmp_path: Path):
        """Returns False when cloud directory doesn't exist."""
        manager = BackupManager(
            db_path=tmp_path / "db.db",
            backup_path=tmp_path / "backups",
            cloud_sync_path=tmp_path / "nonexistent_cloud",
        )
        assert manager.sync_to_cloud() is False

    def test_sync_no_backups(self, tmp_path: Path):
        """Returns False when no backups to sync."""
        cloud_dir = tmp_path / "onedrive"
        cloud_dir.mkdir()

        manager = BackupManager(
            db_path=tmp_path / "db.db",
            backup_path=tmp_path / "empty_backups",
            cloud_sync_path=cloud_dir,
        )
        assert manager.sync_to_cloud() is False


# =========================================================================
# FILENAME PARSING TESTS
# =========================================================================


class TestFilenameParsing:
    """Test backup filename generation and parsing."""

    def test_generated_filename_format(self, tmp_path: Path):
        """Filename follows ironlung3_YYYYMMDD_HHMMSS_label.db format."""
        db_path = tmp_path / "source.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        manager = BackupManager(db_path=db_path, backup_path=tmp_path / "backups")
        path = manager.create_backup(label="manual")

        parts = path.stem.split("_")
        assert parts[0] == "ironlung3"
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 6  # HHMMSS
        assert parts[3] == "manual"

    def test_parse_compound_label(self, tmp_path: Path):
        """Parses labels with underscores (e.g. pre_restore)."""
        db_path = tmp_path / "source.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        manager = BackupManager(db_path=db_path, backup_path=tmp_path / "backups")
        path = manager.create_backup(label="pre_restore")

        backups = manager.list_backups()
        assert len(backups) == 1
        assert backups[0].label == "pre_restore"

"""Tests for backup management."""

from pathlib import Path

import pytest

from src.db.backup import BackupInfo, BackupManager


class TestBackupManager:
    """Test BackupManager class."""

    @pytest.mark.skip(reason="Stub not implemented")
    def test_create_backup(self, temp_db, tmp_path: Path):
        """Can create a backup."""
        manager = BackupManager(str(tmp_path / "backups"))
        info = manager.create_backup(temp_db)
        assert info.path.exists()

    @pytest.mark.skip(reason="Stub not implemented")
    def test_list_backups(self, tmp_path: Path):
        """Can list backups."""
        pass

    @pytest.mark.skip(reason="Stub not implemented")
    def test_cleanup_old_backups(self, tmp_path: Path):
        """Cleanup removes old backups."""
        pass

"""Tests for nightly cycle."""

import pytest
from src.autonomous.nightly import run_nightly_cycle, check_last_run


class TestNightlyCycle:
    """Test nightly cycle execution."""
    
    @pytest.mark.skip(reason="Stub not implemented")
    @pytest.mark.slow
    def test_full_cycle_completes(self, memory_db):
        """Full nightly cycle completes without error."""
        pass
    
    @pytest.mark.skip(reason="Stub not implemented")
    def test_cycle_creates_backup(self, memory_db, tmp_path):
        """Nightly cycle creates backup."""
        pass


class TestCheckLastRun:
    """Test last run check."""
    
    @pytest.mark.skip(reason="Stub not implemented")
    def test_returns_none_if_never_run(self, memory_db):
        """Returns None if cycle never ran."""
        result = check_last_run(memory_db)
        assert result is None

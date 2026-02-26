"""Tests for the auto-update module."""

from unittest.mock import MagicMock, patch

import pytest

from src.core.updater import (
    UpdateApplyResult,
    UpdateCheckResult,
    _version_tuple,
    check_for_update,
)


class TestVersionTuple:
    """Test version string parsing."""

    def test_standard_version(self):
        assert _version_tuple("0.7.0") == (0, 7, 0)

    def test_single_digit(self):
        assert _version_tuple("1") == (1,)

    def test_major_minor(self):
        assert _version_tuple("2.3") == (2, 3)

    def test_comparison_newer(self):
        assert _version_tuple("0.8.0") > _version_tuple("0.7.0")

    def test_comparison_same(self):
        assert _version_tuple("0.7.0") == _version_tuple("0.7.0")

    def test_comparison_older(self):
        assert _version_tuple("0.6.0") < _version_tuple("0.7.0")

    def test_invalid_part_treated_as_zero(self):
        assert _version_tuple("1.beta.3") == (1, 0, 3)


class TestCheckForUpdate:
    """Test update checking logic."""

    @patch("src.core.updater._run_git")
    @patch("src.core.updater._get_local_version", return_value="0.7.0")
    def test_fetch_failure_returns_error(self, mock_ver, mock_git):
        """Network failure returns a graceful error."""
        mock_git.return_value = MagicMock(returncode=128, stderr="fatal: unable to access")
        result = check_for_update()
        assert result.error is not None
        assert not result.update_available
        assert result.current_version == "0.7.0"

    @patch("src.core.updater._get_remote_version", return_value="0.8.0")
    @patch("src.core.updater._run_git")
    @patch("src.core.updater._get_local_version", return_value="0.7.0")
    def test_update_available(self, mock_ver, mock_git, mock_remote):
        """Detects when a newer version exists."""
        # fetch succeeds
        fetch_mock = MagicMock(returncode=0, stderr="")
        # rev-list shows 3 commits behind
        revlist_mock = MagicMock(returncode=0, stdout="3\n")
        # log shows commit summary
        log_mock = MagicMock(returncode=0, stdout="abc1234 Fix bug\ndef5678 Add feature\n")
        mock_git.side_effect = [fetch_mock, revlist_mock, log_mock]

        result = check_for_update()
        assert result.update_available is True
        assert result.remote_version == "0.8.0"
        assert result.commits_behind == 3
        assert "Fix bug" in result.commit_summary

    @patch("src.core.updater._get_remote_version", return_value="0.7.0")
    @patch("src.core.updater._run_git")
    @patch("src.core.updater._get_local_version", return_value="0.7.0")
    def test_already_up_to_date(self, mock_ver, mock_git, mock_remote):
        """No update when versions match."""
        fetch_mock = MagicMock(returncode=0, stderr="")
        revlist_mock = MagicMock(returncode=0, stdout="0\n")
        mock_git.side_effect = [fetch_mock, revlist_mock]

        result = check_for_update()
        assert result.update_available is False
        assert result.current_version == "0.7.0"
        assert result.error is None


class TestUpdateCheckResult:
    """Test the result dataclass."""

    def test_defaults(self):
        result = UpdateCheckResult(
            current_version="0.7.0",
            remote_version="0.8.0",
            update_available=True,
            commits_behind=5,
        )
        assert result.error is None
        assert result.commit_summary == ""

    def test_with_error(self):
        result = UpdateCheckResult(
            current_version="0.7.0",
            remote_version=None,
            update_available=False,
            commits_behind=0,
            error="Network error",
        )
        assert result.error == "Network error"


class TestUpdateApplyResult:
    """Test the apply result dataclass."""

    def test_successful_update(self):
        result = UpdateApplyResult(
            success=True,
            old_version="0.7.0",
            new_version="0.8.0",
            message="Updated!",
            needs_restart=True,
        )
        assert result.success
        assert result.needs_restart

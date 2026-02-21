"""Tests for Outlook behavior when msal is not installed.

Verifies that the code raises clear OutlookError (not AttributeError)
when msal is missing.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.core.config import Config
from src.core.exceptions import OutlookError
from src.integrations.outlook import OutlookClient


@pytest.fixture
def outlook_config(tmp_path, monkeypatch):
    """Provide OutlookClient with test credentials configured."""
    config = Config(
        db_path=tmp_path / "test.db",
        backup_path=tmp_path / "backups",
        log_path=tmp_path / "logs",
        outlook_client_id="test-client-id",
        outlook_client_secret="test-client-secret",
        outlook_tenant_id="test-tenant-id",
        outlook_user_email="jeff@nexys.com",
    )
    (tmp_path).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("src.integrations.outlook.get_config", lambda: config)
    return config


class TestMsalNotInstalled:
    """Test that missing msal produces a clear OutlookError, not AttributeError."""

    def test_authenticate_without_msal_raises_outlook_error(self, outlook_config):
        """When msal is None, authenticate raises OutlookError with install hint."""
        with patch("src.integrations.outlook.msal", None):
            client = OutlookClient()
            with pytest.raises(OutlookError, match="msal package not installed"):
                client.authenticate()

    def test_health_check_without_msal_returns_false(self, outlook_config):
        """When msal is None, health_check returns False (not an unhandled error)."""
        with patch("src.integrations.outlook.msal", None):
            client = OutlookClient()
            assert client.health_check() is False

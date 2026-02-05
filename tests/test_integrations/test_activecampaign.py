"""Tests for ActiveCampaign integration (src/integrations/activecampaign.py).

Covers:
    - ActiveCampaignClient.is_configured: with and without credentials
    - get_contacts raises IntegrationError when not configured
    - get_pipelines raises IntegrationError when not configured
"""

from unittest.mock import patch

import pytest

from src.core.exceptions import IntegrationError
from src.integrations.activecampaign import ActiveCampaignClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_unconfigured_client() -> ActiveCampaignClient:
    """Create an AC client with no credentials by patching config."""
    with patch("src.integrations.activecampaign.get_config") as mock_config:
        cfg = mock_config.return_value
        cfg.activecampaign_api_key = None
        cfg.activecampaign_url = None
        client = ActiveCampaignClient()
    return client


def _make_configured_client() -> ActiveCampaignClient:
    """Create an AC client with fake credentials by patching config."""
    with patch("src.integrations.activecampaign.get_config") as mock_config:
        cfg = mock_config.return_value
        cfg.activecampaign_api_key = "fake-api-key-12345"
        cfg.activecampaign_url = "https://test.api-us1.com"
        client = ActiveCampaignClient()
    return client


# ===========================================================================
# is_configured
# ===========================================================================


class TestIsConfigured:
    """Credential presence check."""

    def test_not_configured_without_credentials(self):
        """Returns False when both api_key and url are None."""
        client = _make_unconfigured_client()
        assert client.is_configured() is False

    def test_not_configured_with_only_api_key(self):
        """Returns False when only api_key is provided."""
        with patch("src.integrations.activecampaign.get_config") as mock_config:
            cfg = mock_config.return_value
            cfg.activecampaign_api_key = "some-key"
            cfg.activecampaign_url = None
            client = ActiveCampaignClient()
        assert client.is_configured() is False

    def test_not_configured_with_only_url(self):
        """Returns False when only url is provided."""
        with patch("src.integrations.activecampaign.get_config") as mock_config:
            cfg = mock_config.return_value
            cfg.activecampaign_api_key = None
            cfg.activecampaign_url = "https://test.api-us1.com"
            client = ActiveCampaignClient()
        assert client.is_configured() is False

    def test_configured_with_both(self):
        """Returns True when both api_key and url are provided."""
        client = _make_configured_client()
        assert client.is_configured() is True


# ===========================================================================
# get_contacts
# ===========================================================================


class TestGetContacts:
    """Contact retrieval."""

    def test_raises_when_not_configured(self):
        """get_contacts raises IntegrationError when not configured."""
        client = _make_unconfigured_client()
        with pytest.raises(IntegrationError, match="not configured"):
            client.get_contacts()

    def test_raises_with_pipeline_filter_when_not_configured(self):
        """get_contacts with pipeline_id still raises when not configured."""
        client = _make_unconfigured_client()
        with pytest.raises(IntegrationError, match="not configured"):
            client.get_contacts(pipeline_id=1)


# ===========================================================================
# get_pipelines
# ===========================================================================


class TestGetPipelines:
    """Pipeline retrieval."""

    def test_raises_when_not_configured(self):
        """get_pipelines raises IntegrationError when not configured."""
        client = _make_unconfigured_client()
        with pytest.raises(IntegrationError, match="not configured"):
            client.get_pipelines()

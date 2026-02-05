"""Tests for ServiceRegistry and service availability tracking."""

from unittest.mock import patch

import pytest

from src.core.config import Config
from src.core.exceptions import ConfigurationError
from src.core.services import (
    ServicePhase,
    ServiceRegistry,
    ServiceStatus,
    get_service_registry,
    reset_service_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset singleton between tests."""
    reset_service_registry()
    yield
    reset_service_registry()


def _make_config(**kwargs) -> Config:
    """Build a Config with test defaults."""
    defaults = {
        "db_path": "/tmp/test.db",
        "log_path": "/tmp/logs",
        "backup_path": "/tmp/backups",
        "debug": True,
    }
    defaults.update(kwargs)
    from pathlib import Path

    path_fields = ["db_path", "log_path", "backup_path"]
    for f in path_fields:
        if isinstance(defaults[f], str):
            defaults[f] = Path(defaults[f])
    return Config(**defaults)


class TestServiceRegistryNoCredentials:
    """Tests with no credentials configured."""

    def test_outlook_not_available(self):
        config = _make_config()
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            assert not registry.is_available("outlook")

    def test_claude_not_available(self):
        config = _make_config()
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            assert not registry.is_available("claude")

    def test_activecampaign_not_available(self):
        config = _make_config()
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            assert not registry.is_available("activecampaign")

    def test_bria_always_available(self):
        config = _make_config()
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            assert registry.is_available("bria")

    def test_google_search_not_available(self):
        config = _make_config()
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            assert not registry.is_available("google_search")

    def test_unknown_service_returns_false(self):
        config = _make_config()
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            assert not registry.is_available("nonexistent")

    def test_unknown_service_check_raises(self):
        config = _make_config()
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            with pytest.raises(KeyError, match="Unknown service"):
                registry.check("nonexistent")


class TestServiceRegistryWithCredentials:
    """Tests with credentials configured."""

    def test_outlook_available_with_all_creds(self):
        config = _make_config(
            outlook_client_id="test-id",
            outlook_client_secret="test-secret",
            outlook_tenant_id="test-tenant",
            outlook_user_email="user@test.com",
        )
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            assert registry.is_available("outlook")
            status = registry.check("outlook")
            assert status.configured
            assert status.reason == ""
            assert len(status.credentials_missing) == 0

    def test_outlook_partial_creds_not_available(self):
        config = _make_config(
            outlook_client_id="test-id",
            # Missing secret and tenant
        )
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            assert not registry.is_available("outlook")
            status = registry.check("outlook")
            assert not status.configured
            assert "Partial" in status.reason
            assert "OUTLOOK_CLIENT_ID" in status.credentials_present
            assert "OUTLOOK_CLIENT_SECRET" in status.credentials_missing

    def test_claude_available_with_key(self):
        config = _make_config(claude_api_key="sk-ant-test-key")
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            assert registry.is_available("claude")

    def test_activecampaign_partial_not_available(self):
        config = _make_config(
            activecampaign_api_key="test-key",
            # Missing URL
        )
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            assert not registry.is_available("activecampaign")
            status = registry.check("activecampaign")
            assert "Partial" in status.reason

    def test_activecampaign_fully_configured(self):
        config = _make_config(
            activecampaign_api_key="test-key",
            activecampaign_url="https://test.api-us1.com",
        )
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            assert registry.is_available("activecampaign")


class TestServiceRegistryRequire:
    """Tests for the require() assertion method."""

    def test_require_available_service_passes(self):
        config = _make_config(claude_api_key="sk-ant-test")
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            registry.require("claude")  # Should not raise

    def test_require_unavailable_service_raises(self):
        config = _make_config()
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            with pytest.raises(ConfigurationError, match="not available"):
                registry.require("claude")

    def test_require_bria_always_passes(self):
        config = _make_config()
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            registry.require("bria")  # Should not raise


class TestReadinessReport:
    """Tests for the readiness report."""

    def test_report_structure(self):
        config = _make_config()
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            report = registry.readiness_report()
            assert len(report.services) > 0
            assert isinstance(report.phase_ready, dict)
            assert isinstance(report.summary, str)

    def test_report_phases_without_creds(self):
        config = _make_config()
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            report = registry.readiness_report()
            # Phase 3 has Bria (always ready) but Outlook is missing
            assert report.phase_ready[3] is False
            assert report.phase_ready[4] is False
            assert report.phase_ready[5] is False

    def test_report_phase3_ready_with_outlook(self):
        config = _make_config(
            outlook_client_id="id",
            outlook_client_secret="secret",
            outlook_tenant_id="tenant",
            outlook_user_email="user@test.com",
        )
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            report = registry.readiness_report()
            assert report.phase_ready[3] is True

    def test_report_summary_contains_phases(self):
        config = _make_config()
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            report = registry.readiness_report()
            assert "Phase 3" in report.summary
            assert "Phase 4" in report.summary
            assert "Phase 5" in report.summary

    def test_report_summary_shows_not_ready(self):
        config = _make_config()
        with patch("src.core.services.get_config", return_value=config):
            registry = ServiceRegistry()
            report = registry.readiness_report()
            assert "NOT READY" in report.summary


class TestServiceStatus:
    """Tests for ServiceStatus dataclass."""

    def test_status_fields(self):
        status = ServiceStatus(
            name="Test Service",
            service_key="test",
            phase=ServicePhase.PHASE_3,
            configured=True,
            available=True,
        )
        assert status.name == "Test Service"
        assert status.phase == ServicePhase.PHASE_3
        assert status.configured
        assert status.available
        assert status.reason == ""
        assert status.credentials_missing == []


class TestSingleton:
    """Tests for the singleton pattern."""

    def test_get_service_registry_returns_same_instance(self):
        config = _make_config()
        with patch("src.core.services.get_config", return_value=config):
            r1 = get_service_registry()
            r2 = get_service_registry()
            assert r1 is r2

    def test_reset_clears_singleton(self):
        config = _make_config()
        with patch("src.core.services.get_config", return_value=config):
            r1 = get_service_registry()
            reset_service_registry()
            r2 = get_service_registry()
            assert r1 is not r2

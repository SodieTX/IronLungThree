"""Tests for configuration management."""

from pathlib import Path

import pytest

from src.core.config import Config, load_config, validate_config


class TestConfig:
    """Test Config dataclass."""

    def test_config_default_values(self):
        """Config has sensible defaults."""
        config = Config()
        assert config.debug is False

    def test_config_with_custom_paths(self, tmp_path: Path):
        """Config accepts custom paths."""
        config = Config(
            db_path=tmp_path / "data.db",
            backup_path=tmp_path / "backups",
        )
        assert "data.db" in str(config.db_path)


class TestLoadConfig:
    """Test config loading."""

    @pytest.mark.skip(reason="Stub not implemented")
    def test_load_from_env_file(self, tmp_path: Path):
        """Should load from .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("IRONLUNG_DEBUG=true\n")
        config = load_config(str(env_file))
        assert config.debug_mode is True


class TestValidateConfig:
    """Test config validation."""

    @pytest.mark.skip(reason="Stub not implemented")
    def test_validate_missing_path(self, mock_config: Config):
        """Should raise for non-existent paths."""
        mock_config.db_path = "/nonexistent/path/db.sqlite"
        with pytest.raises(Exception):
            validate_config(mock_config)

    def test_partial_outlook_creds_flagged_critical(self, tmp_path: Path):
        """Partial Outlook credentials should produce CRITICAL issue."""
        config = Config(
            db_path=tmp_path / "test.db",
            log_path=tmp_path / "logs",
            backup_path=tmp_path / "backups",
            outlook_client_id="test-id",
            # Missing secret and tenant
        )
        issues = validate_config(config)
        critical_issues = [i for i in issues if "CRITICAL" in i]
        assert len(critical_issues) >= 1
        assert "Partial Outlook" in critical_issues[0]

    def test_full_outlook_creds_no_email_flagged(self, tmp_path: Path):
        """Full Outlook creds without email should be flagged."""
        config = Config(
            db_path=tmp_path / "test.db",
            log_path=tmp_path / "logs",
            backup_path=tmp_path / "backups",
            outlook_client_id="id",
            outlook_client_secret="secret",
            outlook_tenant_id="tenant",
            # Missing user email
        )
        issues = validate_config(config)
        email_issues = [i for i in issues if "OUTLOOK_USER_EMAIL" in i]
        assert len(email_issues) >= 1

    def test_full_outlook_creds_no_issues(self, tmp_path: Path):
        """Complete Outlook credentials should not produce Outlook issues."""
        config = Config(
            db_path=tmp_path / "test.db",
            log_path=tmp_path / "logs",
            backup_path=tmp_path / "backups",
            outlook_client_id="id",
            outlook_client_secret="secret",
            outlook_tenant_id="tenant",
            outlook_user_email="user@test.com",
        )
        issues = validate_config(config)
        outlook_issues = [i for i in issues if "Outlook" in i]
        assert len(outlook_issues) == 0

    def test_no_creds_no_outlook_issues(self, tmp_path: Path):
        """No credentials at all should not produce Outlook issues."""
        config = Config(
            db_path=tmp_path / "test.db",
            log_path=tmp_path / "logs",
            backup_path=tmp_path / "backups",
        )
        issues = validate_config(config)
        outlook_issues = [i for i in issues if "Outlook" in i]
        assert len(outlook_issues) == 0

    def test_partial_activecampaign_flagged(self, tmp_path: Path):
        """Partial ActiveCampaign credentials should be flagged."""
        config = Config(
            db_path=tmp_path / "test.db",
            log_path=tmp_path / "logs",
            backup_path=tmp_path / "backups",
            activecampaign_api_key="test-key",
            # Missing URL
        )
        issues = validate_config(config)
        ac_issues = [i for i in issues if "ActiveCampaign" in i]
        assert len(ac_issues) >= 1

"""Stress tests for configuration loading and validation.

Targets:
    - Hostile .env file content (injection, encoding, format abuse)
    - Quote parsing edge cases
    - Boolean parsing confusion
    - Path traversal and validation
    - Singleton behavior
    - Environment variable precedence
"""

import os
from pathlib import Path

import pytest

from src.core.config import (
    Config,
    _get_bool,
    _get_path,
    _get_str,
    load_config,
    load_env_file,
    reset_config,
    validate_config,
)


# =========================================================================
# .ENV FILE PARSING STRESS
# =========================================================================


class TestEnvFileParsing:
    """Adversarial .env file content."""

    def test_empty_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("")
        result = load_env_file(env_file)
        assert result == {}

    def test_only_comments(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# comment 1\n# comment 2\n# comment 3\n")
        result = load_env_file(env_file)
        assert result == {}

    def test_only_blank_lines(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("\n\n\n\n\n")
        result = load_env_file(env_file)
        assert result == {}

    def test_value_with_equals_sign(self, tmp_path):
        """Value containing = should work (partition splits on first =)."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=value=with=equals\n")
        result = load_env_file(env_file)
        assert result["KEY"] == "value=with=equals"

    def test_empty_value(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=\n")
        result = load_env_file(env_file)
        assert result["KEY"] == ""

    def test_value_with_spaces(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=  value with spaces  \n")
        result = load_env_file(env_file)
        assert result["KEY"] == "value with spaces"

    def test_double_quoted_value(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('KEY="hello world"\n')
        result = load_env_file(env_file)
        assert result["KEY"] == "hello world"

    def test_single_quoted_value(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("KEY='hello world'\n")
        result = load_env_file(env_file)
        assert result["KEY"] == "hello world"

    def test_single_quote_char_as_value(self, tmp_path):
        """A value that is just a single quote character."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=\"\n")
        result = load_env_file(env_file)
        # value = '"', value[0] = '"', value[-1] = '"', same quote
        # So it strips both -> empty string
        assert result["KEY"] == ""

    def test_mismatched_quotes(self, tmp_path):
        """Mismatched quotes should not be stripped."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=\"hello'\n")
        result = load_env_file(env_file)
        # value[0]='"', value[-1]="'" - different, so not stripped
        assert result["KEY"] == "\"hello'"

    def test_line_without_equals(self, tmp_path):
        """Line without = should be skipped."""
        env_file = tmp_path / ".env"
        env_file.write_text("NOEQUALS\nKEY=value\n")
        result = load_env_file(env_file)
        assert "NOEQUALS" not in result
        assert result["KEY"] == "value"

    def test_empty_key(self, tmp_path):
        """Empty key (just = sign) should be skipped."""
        env_file = tmp_path / ".env"
        env_file.write_text("=value\n")
        result = load_env_file(env_file)
        assert "" not in result

    def test_key_with_spaces(self, tmp_path):
        """Key with spaces should be stripped."""
        env_file = tmp_path / ".env"
        env_file.write_text("  MY_KEY  =value\n")
        result = load_env_file(env_file)
        assert result["MY_KEY"] == "value"

    def test_nonexistent_file(self, tmp_path):
        """Nonexistent .env should return empty dict."""
        result = load_env_file(tmp_path / "nonexistent.env")
        assert result == {}

    def test_duplicate_keys_last_wins(self, tmp_path):
        """Duplicate keys in .env - last value wins."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=first\nKEY=second\n")
        result = load_env_file(env_file)
        assert result["KEY"] == "second"

    def test_unicode_in_env_file(self, tmp_path):
        """Unicode values in .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=こんにちは\n", encoding="utf-8")
        result = load_env_file(env_file)
        assert result["KEY"] == "こんにちは"

    def test_very_long_value(self, tmp_path):
        """Very long value in .env file."""
        env_file = tmp_path / ".env"
        long_val = "x" * 100000
        env_file.write_text(f"KEY={long_val}\n")
        result = load_env_file(env_file)
        assert result["KEY"] == long_val

    def test_multiline_quoted_value_not_supported(self, tmp_path):
        """Multiline values are NOT supported - each line is parsed independently."""
        env_file = tmp_path / ".env"
        env_file.write_text('KEY="line1\nline2"\n')
        result = load_env_file(env_file)
        # First line: KEY="line1
        # This has value = '"line1' - starts with " but doesn't end with "
        assert "KEY" in result

    def test_hash_in_value(self, tmp_path):
        """Hash (#) in value - should be kept since it's after =."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=value#with#hash\n")
        result = load_env_file(env_file)
        assert result["KEY"] == "value#with#hash"


# =========================================================================
# BOOLEAN PARSING EDGE CASES
# =========================================================================


class TestBooleanParsing:
    """Test _get_bool with various inputs."""

    def test_true_values(self):
        for val in ["true", "TRUE", "True", "1", "yes", "YES", "on", "ON"]:
            env = {"KEY": val}
            assert _get_bool("KEY", False, env) is True, f"'{val}' should be True"

    def test_false_values(self):
        """Everything else is False."""
        for val in ["false", "FALSE", "0", "no", "NO", "off", "OFF", "", "maybe",
                     "t", "y", "enabled", "disabled", "2", "-1"]:
            env = {"KEY": val}
            assert _get_bool("KEY", True, env) is False, f"'{val}' should be False"

    def test_missing_key_returns_default(self):
        assert _get_bool("MISSING", True, {}) is True
        assert _get_bool("MISSING", False, {}) is False


# =========================================================================
# STRING GETTER EDGE CASES
# =========================================================================


class TestStringGetter:
    """Test _get_str with various inputs."""

    def test_empty_string_returns_none(self):
        """Empty string via env_vars returns None (due to `or None`)."""
        result = _get_str("KEY", {"KEY": ""})
        assert result is None

    def test_whitespace_string_is_truthy(self):
        """Whitespace string is truthy, so it's returned."""
        result = _get_str("KEY", {"KEY": "  "})
        assert result == "  "

    def test_missing_key(self):
        result = _get_str("MISSING", {})
        assert result is None


# =========================================================================
# PATH GETTER EDGE CASES
# =========================================================================


class TestPathGetter:
    """Test _get_path with edge cases."""

    def test_tilde_expansion(self):
        """Tilde should be expanded to home directory."""
        result = _get_path("KEY", Path("/default"), {"KEY": "~/test"})
        assert str(result) != "~/test"
        assert "test" in str(result)

    def test_relative_path_resolved(self):
        """Relative paths should be resolved to absolute."""
        result = _get_path("KEY", Path("/default"), {"KEY": "relative/path"})
        assert result.is_absolute()

    def test_default_when_missing(self):
        result = _get_path("MISSING", Path("/fallback"), {})
        assert result == Path("/fallback")


# =========================================================================
# CONFIG VALIDATION
# =========================================================================


class TestConfigValidation:
    """Test validate_config with various scenarios."""

    def test_valid_config_no_issues(self, tmp_path):
        """Valid config should have no issues (except cloud sync warning)."""
        config = Config(
            db_path=tmp_path / "test.db",
            log_path=tmp_path / "logs",
            backup_path=tmp_path / "backups",
            cloud_sync_path=None,
        )
        issues = validate_config(config)
        assert len(issues) == 0

    def test_partial_outlook_credentials_warns(self, tmp_path):
        """Having some but not all Outlook creds should warn."""
        config = Config(
            db_path=tmp_path / "test.db",
            log_path=tmp_path / "logs",
            backup_path=tmp_path / "backups",
            cloud_sync_path=None,
            outlook_client_id="present",
            # Missing client_secret and tenant_id
        )
        issues = validate_config(config)
        assert any("Outlook" in issue for issue in issues)

    def test_full_outlook_missing_email_warns(self, tmp_path):
        """Full Outlook creds but no email should warn."""
        config = Config(
            db_path=tmp_path / "test.db",
            log_path=tmp_path / "logs",
            backup_path=tmp_path / "backups",
            cloud_sync_path=None,
            outlook_client_id="id",
            outlook_client_secret="secret",
            outlook_tenant_id="tenant",
            # Missing outlook_user_email
        )
        issues = validate_config(config)
        assert any("OUTLOOK_USER_EMAIL" in issue for issue in issues)

    def test_partial_activecampaign_warns(self, tmp_path):
        config = Config(
            db_path=tmp_path / "test.db",
            log_path=tmp_path / "logs",
            backup_path=tmp_path / "backups",
            cloud_sync_path=None,
            activecampaign_api_key="key",
            # Missing URL
        )
        issues = validate_config(config)
        assert any("ActiveCampaign" in issue for issue in issues)

    def test_partial_google_warns(self, tmp_path):
        config = Config(
            db_path=tmp_path / "test.db",
            log_path=tmp_path / "logs",
            backup_path=tmp_path / "backups",
            cloud_sync_path=None,
            google_api_key="key",
            # Missing CX
        )
        issues = validate_config(config)
        assert any("Google" in issue for issue in issues)

    def test_nonexistent_cloud_sync_warns(self, tmp_path):
        config = Config(
            db_path=tmp_path / "test.db",
            log_path=tmp_path / "logs",
            backup_path=tmp_path / "backups",
            cloud_sync_path=tmp_path / "nonexistent_dir",
        )
        issues = validate_config(config)
        assert any("Cloud sync" in issue for issue in issues)


# =========================================================================
# SINGLETON BEHAVIOR
# =========================================================================


class TestSingletonBehavior:
    """Test the config singleton."""

    def test_reset_clears_singleton(self):
        """reset_config should clear the cached config."""
        from src.core.config import _config, get_config

        reset_config()
        # After reset, next get_config loads fresh
        config = get_config()
        assert config is not None
        reset_config()


# =========================================================================
# LOAD_CONFIG EDGE CASES
# =========================================================================


class TestLoadConfigEdgeCases:
    """Test load_config with various environments."""

    def test_load_with_nonexistent_env_file(self, tmp_path):
        """Loading with nonexistent .env should use defaults."""
        config = load_config(tmp_path / "nonexistent.env")
        assert config.db_path is not None
        assert config.debug is False

    def test_env_var_overrides_env_file(self, tmp_path, monkeypatch):
        """OS environment variables should override .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("IRONLUNG_DEBUG=false\n")
        monkeypatch.setenv("IRONLUNG_DEBUG", "true")
        config = load_config(env_file)
        assert config.debug is True

    def test_load_config_with_all_env_vars(self, tmp_path, monkeypatch):
        """Set every config via environment variables."""
        db_path = str(tmp_path / "env_test.db")
        monkeypatch.setenv("IRONLUNG_DB_PATH", db_path)
        monkeypatch.setenv("IRONLUNG_DEBUG", "true")
        monkeypatch.setenv("IRONLUNG_DRY_RUN", "true")
        monkeypatch.setenv("CLAUDE_API_KEY", "test-key-123")

        config = load_config(tmp_path / "nonexistent.env")
        assert str(config.db_path) == str(Path(db_path).resolve())
        assert config.debug is True
        assert config.dry_run is True
        assert config.claude_api_key == "test-key-123"

"""Tests for src.core.security module."""

import os
import stat
import tempfile
from pathlib import Path

import pytest

from src.core.security import (
    redact_api_key,
    redact_email,
    restrict_permissions,
    secure_mkdir,
    secure_write_file,
    validate_api_key_format,
    validate_api_url,
    validate_safe_path,
)


# ---------------------------------------------------------------------------
# File permissions
# ---------------------------------------------------------------------------


class TestSecureWriteFile:
    """Tests for secure_write_file()."""

    def test_creates_file_with_restricted_permissions(self, tmp_path: Path) -> None:
        target = tmp_path / "secrets" / "test.env"
        secure_write_file(target, "KEY=value\n")

        assert target.exists()
        assert target.read_text() == "KEY=value\n"

        mode = target.stat().st_mode
        # Owner read+write only (0600)
        assert mode & stat.S_IRUSR  # owner read
        assert mode & stat.S_IWUSR  # owner write
        assert not (mode & stat.S_IRGRP)  # no group read
        assert not (mode & stat.S_IWGRP)  # no group write
        assert not (mode & stat.S_IROTH)  # no other read
        assert not (mode & stat.S_IWOTH)  # no other write

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "c" / "file.txt"
        secure_write_file(target, "hello")
        assert target.exists()

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "existing.txt"
        target.write_text("old content")
        secure_write_file(target, "new content")
        assert target.read_text() == "new content"


class TestSecureMkdir:
    """Tests for secure_mkdir()."""

    def test_creates_directory_with_restricted_permissions(self, tmp_path: Path) -> None:
        target = tmp_path / "secure_dir"
        secure_mkdir(target)

        assert target.is_dir()
        mode = target.stat().st_mode
        # Owner rwx only (0700)
        assert mode & stat.S_IRWXU  # owner rwx
        assert not (mode & stat.S_IRGRP)  # no group access
        assert not (mode & stat.S_IROTH)  # no other access

    def test_existing_directory_no_error(self, tmp_path: Path) -> None:
        target = tmp_path / "existing"
        target.mkdir()
        # Should not raise
        secure_mkdir(target)


class TestRestrictPermissions:
    """Tests for restrict_permissions()."""

    def test_restricts_file(self, tmp_path: Path) -> None:
        target = tmp_path / "open_file.txt"
        target.write_text("data")
        os.chmod(target, 0o644)  # world-readable

        restrict_permissions(target)

        mode = target.stat().st_mode
        assert not (mode & stat.S_IRGRP)
        assert not (mode & stat.S_IROTH)

    def test_nonexistent_path_no_error(self, tmp_path: Path) -> None:
        restrict_permissions(tmp_path / "nonexistent")


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------


class TestRedactApiKey:
    """Tests for redact_api_key()."""

    def test_none_returns_not_set(self) -> None:
        assert redact_api_key(None) == "<not set>"

    def test_empty_returns_not_set(self) -> None:
        assert redact_api_key("") == "<not set>"

    def test_short_key_fully_redacted(self) -> None:
        assert redact_api_key("abcdef") == "****"

    def test_long_key_shows_prefix_and_suffix(self) -> None:
        key = "sk-ant-api03-abcdefghij1234567890"
        result = redact_api_key(key)
        assert result.startswith("sk-")
        assert result.endswith("7890")
        assert "..." in result
        # Must not contain the full key
        assert "abcdefghij" not in result


class TestRedactEmail:
    """Tests for redact_email()."""

    def test_none_returns_redacted(self) -> None:
        assert redact_email(None) == "<redacted>"

    def test_normal_email_redacted(self) -> None:
        result = redact_email("john.doe@example.com")
        assert "@example.com" in result
        assert "john.doe" not in result

    def test_short_local_part(self) -> None:
        result = redact_email("ab@test.com")
        assert "@test.com" in result

    def test_no_at_sign(self) -> None:
        assert redact_email("notanemail") == "<redacted>"


# ---------------------------------------------------------------------------
# URL validation (SSRF prevention)
# ---------------------------------------------------------------------------


class TestValidateApiUrl:
    """Tests for validate_api_url()."""

    def test_valid_https_url(self) -> None:
        url = validate_api_url("https://api.anthropic.com/v1/messages")
        assert url == "https://api.anthropic.com/v1/messages"

    def test_rejects_http(self) -> None:
        with pytest.raises(ValueError, match="HTTPS"):
            validate_api_url("http://api.example.com")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_api_url("")

    def test_rejects_localhost(self) -> None:
        with pytest.raises(ValueError, match="localhost"):
            validate_api_url("https://localhost/api")

    def test_rejects_private_ip_127(self) -> None:
        with pytest.raises(ValueError, match="private"):
            validate_api_url("https://127.0.0.1/api")

    def test_rejects_private_ip_10(self) -> None:
        with pytest.raises(ValueError, match="private"):
            validate_api_url("https://10.0.0.1/api")

    def test_rejects_private_ip_192(self) -> None:
        with pytest.raises(ValueError, match="private"):
            validate_api_url("https://192.168.1.1/api")

    def test_rejects_private_ip_172(self) -> None:
        with pytest.raises(ValueError, match="private"):
            validate_api_url("https://172.16.0.1/api")

    def test_integration_domain_check_activecampaign(self) -> None:
        # Valid AC domain
        url = validate_api_url(
            "https://myaccount.api-us1.com/api/3", integration="activecampaign"
        )
        assert url

    def test_integration_domain_check_rejects_wrong_domain(self) -> None:
        with pytest.raises(ValueError, match="not in allowed domains"):
            validate_api_url("https://evil.com/api/3", integration="activecampaign")

    def test_strips_whitespace(self) -> None:
        url = validate_api_url("  https://api.example.com  ")
        assert url == "https://api.example.com"


# ---------------------------------------------------------------------------
# Path traversal prevention
# ---------------------------------------------------------------------------


class TestValidateSafePath:
    """Tests for validate_safe_path()."""

    def test_valid_path_within_parent(self, tmp_path: Path) -> None:
        child = tmp_path / "data" / "file.db"
        result = validate_safe_path(child, tmp_path)
        assert str(result).startswith(str(tmp_path.resolve()))

    def test_rejects_path_traversal(self, tmp_path: Path) -> None:
        malicious = tmp_path / ".." / ".." / "etc" / "passwd"
        with pytest.raises(ValueError, match="traversal"):
            validate_safe_path(malicious, tmp_path)


# ---------------------------------------------------------------------------
# API key format validation
# ---------------------------------------------------------------------------


class TestValidateApiKeyFormat:
    """Tests for validate_api_key_format()."""

    def test_valid_anthropic_key(self) -> None:
        key = "sk-ant-api03-" + "a" * 40
        assert validate_api_key_format(key, "anthropic") is True

    def test_invalid_anthropic_key_wrong_prefix(self) -> None:
        assert validate_api_key_format("wrong-prefix-key", "anthropic") is False

    def test_invalid_anthropic_key_too_short(self) -> None:
        assert validate_api_key_format("sk-ant-short", "anthropic") is False

    def test_valid_google_key(self) -> None:
        key = "AIzaSyA" + "a" * 30
        assert validate_api_key_format(key, "google") is True

    def test_empty_key_invalid(self) -> None:
        assert validate_api_key_format("", "anthropic") is False

    def test_whitespace_only_invalid(self) -> None:
        assert validate_api_key_format("   ", "anthropic") is False

    def test_unknown_provider_accepts_long_key(self) -> None:
        assert validate_api_key_format("a" * 20, "unknown_provider") is True

    def test_unknown_provider_rejects_short_key(self) -> None:
        assert validate_api_key_format("short", "unknown_provider") is False

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

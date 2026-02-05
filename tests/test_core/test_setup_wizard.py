"""Tests for first-run setup wizard."""

from pathlib import Path

import pytest

from src.core.setup_wizard import SetupConfig, SetupWizard


@pytest.fixture
def wizard(tmp_path: Path) -> SetupWizard:
    return SetupWizard(data_dir=tmp_path)


class TestSetupWizard:
    def test_needs_setup_initially(self, wizard: SetupWizard) -> None:
        assert wizard.needs_setup() is True
        assert wizard.is_setup_complete() is False

    def test_set_user_name(self, wizard: SetupWizard) -> None:
        wizard.set_user_name("Jeff")
        assert wizard.get_config().user_name == "Jeff"

    def test_set_user_name_strips_whitespace(self, wizard: SetupWizard) -> None:
        wizard.set_user_name("  Jeff  ")
        assert wizard.get_config().user_name == "Jeff"

    def test_set_db_path(self, wizard: SetupWizard) -> None:
        wizard.set_db_path("/custom/path.db")
        assert wizard.get_config().db_path == "/custom/path.db"

    def test_set_backup_dir(self, wizard: SetupWizard) -> None:
        wizard.set_backup_dir("/backups")
        assert wizard.get_config().backup_dir == "/backups"

    def test_set_sounds(self, wizard: SetupWizard) -> None:
        wizard.set_sounds_enabled(False)
        assert wizard.get_config().sounds_enabled is False

    def test_set_outlook(self, wizard: SetupWizard) -> None:
        wizard.set_outlook_configured(True)
        assert wizard.get_config().outlook_configured is True

    def test_complete_setup(self, wizard: SetupWizard) -> None:
        wizard.set_user_name("Jeff")
        config = wizard.complete_setup()
        assert config.setup_complete is True
        assert wizard.is_setup_complete() is True
        assert wizard.needs_setup() is False

    def test_persistence(self, tmp_path: Path) -> None:
        w1 = SetupWizard(data_dir=tmp_path)
        w1.set_user_name("Jeff")
        w1.set_sounds_enabled(False)
        w1.complete_setup()

        w2 = SetupWizard(data_dir=tmp_path)
        assert w2.is_setup_complete() is True
        config = w2.get_config()
        assert config.user_name == "Jeff"
        assert config.sounds_enabled is False

    def test_reset(self, wizard: SetupWizard) -> None:
        wizard.set_user_name("Jeff")
        wizard.complete_setup()
        wizard.reset()
        assert wizard.needs_setup() is True
        assert wizard.get_config().user_name == ""

    def test_corrupt_config_uses_defaults(self, tmp_path: Path) -> None:
        (tmp_path / "setup_config.json").write_text("broken", encoding="utf-8")
        wizard = SetupWizard(data_dir=tmp_path)
        assert wizard.needs_setup() is True

    def test_default_config_values(self, wizard: SetupWizard) -> None:
        config = wizard.get_config()
        assert config.user_name == ""
        assert config.db_path == "data/ironlung.db"
        assert config.backup_dir == "data/backups"
        assert config.sounds_enabled is True
        assert config.outlook_configured is False
        assert config.setup_complete is False

"""Tests for the install wizard GUI module.

Tests the InstallWizard logic without requiring a live tkinter display.
Tkinter widget creation is tested where possible; full mainloop is not.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

try:
    import tkinter as tk

    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

if HAS_TKINTER:
    from src.gui.install_wizard import InstallWizard, _NUM_STEPS

pytestmark = pytest.mark.skipif(not HAS_TKINTER, reason="tkinter not available")


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def wizard(data_dir: Path) -> InstallWizard:
    return InstallWizard(data_dir=data_dir)


class TestInstallWizardInit:
    def test_initial_step_is_zero(self, wizard: InstallWizard) -> None:
        assert wizard.current_step == 0

    def test_setup_wizard_accessible(self, wizard: InstallWizard) -> None:
        assert wizard.setup_wizard is not None
        assert wizard.setup_wizard.needs_setup() is True

    def test_result_is_none_before_run(self, wizard: InstallWizard) -> None:
        assert wizard._result is None


class TestInstallWizardSteps:
    """Test step count constant."""

    def test_num_steps(self) -> None:
        assert _NUM_STEPS == 5


class TestInstallWizardNavigation:
    """Test navigation logic without mainloop."""

    @patch("src.gui.install_wizard.tk.Tk")
    def test_build_creates_root(self, mock_tk: MagicMock, wizard: InstallWizard) -> None:
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        wizard._build()
        assert wizard._root is mock_root
        mock_root.title.assert_called_once()

    @patch("src.gui.install_wizard.tk.Tk")
    def test_cancel_sets_result_none(self, mock_tk: MagicMock, wizard: InstallWizard) -> None:
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        wizard._build()
        wizard._on_cancel()
        assert wizard._result is None
        mock_root.destroy.assert_called_once()


class TestInstallWizardFinish:
    """Test that finish persists config correctly."""

    @patch("src.gui.install_wizard.tk.Tk")
    def test_finish_persists_config(
        self, mock_tk: MagicMock, data_dir: Path
    ) -> None:
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        wiz = InstallWizard(data_dir=data_dir)
        wiz._build()

        # Set values via tk variables
        assert wiz._var_name is not None
        wiz._var_name.set("Jeff")
        assert wiz._var_sounds is not None
        wiz._var_sounds.set(False)
        assert wiz._var_dry_run is not None
        wiz._var_dry_run.set(True)

        wiz._finish()

        # Check SetupWizard state
        config = wiz.setup_wizard.get_config()
        assert config.setup_complete is True
        assert config.user_name == "Jeff"
        assert config.sounds_enabled is False

    @patch("src.gui.install_wizard.tk.Tk")
    def test_finish_writes_env_file(
        self, mock_tk: MagicMock, data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_root = MagicMock()
        mock_tk.return_value = mock_root

        # Ensure .env goes to tmp
        monkeypatch.chdir(tmp_path)
        env_path = tmp_path / ".env"
        assert not env_path.exists()

        wiz = InstallWizard(data_dir=data_dir)
        wiz._build()
        assert wiz._var_name is not None
        wiz._var_name.set("TestUser")
        assert wiz._var_claude_api_key is not None
        wiz._var_claude_api_key.set("sk-ant-test123")

        wiz._finish()

        assert env_path.exists()
        content = env_path.read_text(encoding="utf-8")
        assert "IRONLUNG_DB_PATH=" in content
        assert "CLAUDE_API_KEY=sk-ant-test123" in content

    @patch("src.gui.install_wizard.tk.Tk")
    def test_finish_skips_existing_env(
        self, mock_tk: MagicMock, data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_root = MagicMock()
        mock_tk.return_value = mock_root

        monkeypatch.chdir(tmp_path)
        env_path = tmp_path / ".env"
        env_path.write_text("EXISTING=true\n", encoding="utf-8")

        wiz = InstallWizard(data_dir=data_dir)
        wiz._build()
        wiz._finish()

        # .env should not be overwritten
        content = env_path.read_text(encoding="utf-8")
        assert "EXISTING=true" in content


class TestInstallWizardOutlook:
    """Test Outlook configuration detection."""

    @patch("src.gui.install_wizard.tk.Tk")
    def test_outlook_configured_when_all_fields_set(
        self, mock_tk: MagicMock, data_dir: Path
    ) -> None:
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        wiz = InstallWizard(data_dir=data_dir)
        wiz._build()

        assert wiz._var_outlook_client_id is not None
        wiz._var_outlook_client_id.set("client-id")
        assert wiz._var_outlook_client_secret is not None
        wiz._var_outlook_client_secret.set("secret")
        assert wiz._var_outlook_tenant_id is not None
        wiz._var_outlook_tenant_id.set("tenant")
        assert wiz._var_outlook_email is not None
        wiz._var_outlook_email.set("user@example.com")

        wiz._finish()
        assert wiz.setup_wizard.get_config().outlook_configured is True

    @patch("src.gui.install_wizard.tk.Tk")
    def test_outlook_not_configured_when_empty(
        self, mock_tk: MagicMock, data_dir: Path
    ) -> None:
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        wiz = InstallWizard(data_dir=data_dir)
        wiz._build()
        wiz._finish()
        assert wiz.setup_wizard.get_config().outlook_configured is False


class TestInstallWizardSetupPersistence:
    """Test that setup_config.json is properly created."""

    @patch("src.gui.install_wizard.tk.Tk")
    def test_config_json_written(self, mock_tk: MagicMock, data_dir: Path) -> None:
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        wiz = InstallWizard(data_dir=data_dir)
        wiz._build()
        assert wiz._var_name is not None
        wiz._var_name.set("Alice")
        wiz._finish()

        config_path = data_dir / "setup_config.json"
        assert config_path.exists()
        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert data["user_name"] == "Alice"
        assert data["setup_complete"] is True

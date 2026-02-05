"""Tests for Bria softphone integration."""

from unittest.mock import MagicMock, patch

import pytest

from src.integrations.bria import BriaDialer


class TestBriaConfig:
    """Test Bria configuration."""

    def test_is_configured_always_true(self):
        """Bria needs no config — always returns True."""
        dialer = BriaDialer()
        assert dialer.is_configured() is True


class TestBriaAvailability:
    """Test Bria detection."""

    def test_is_available_when_found_on_path(self):
        """is_available returns True when Bria is on PATH."""
        dialer = BriaDialer()
        with patch("src.integrations.bria.shutil.which", return_value="/usr/bin/bria"):
            with patch("src.integrations.bria.platform.system", return_value="Linux"):
                result = dialer.is_available()
        assert result is True

    def test_is_available_when_not_found(self):
        """is_available returns False when Bria is not found."""
        dialer = BriaDialer()
        with patch("src.integrations.bria.shutil.which", return_value=None):
            with patch("src.integrations.bria.platform.system", return_value="Linux"):
                result = dialer.is_available()
        assert result is False

    def test_health_check_delegates_to_is_available(self):
        """health_check returns same as is_available."""
        dialer = BriaDialer()
        dialer._available = True
        assert dialer.health_check() is True
        dialer._available = False
        assert dialer.health_check() is False

    def test_availability_is_cached(self):
        """Second call to is_available uses cached result."""
        dialer = BriaDialer()
        dialer._available = True
        # Even without mocking shutil.which, cached value is returned
        assert dialer.is_available() is True


class TestBriaDial:
    """Test dialing functionality."""

    def test_dial_via_bria_when_available(self):
        """dial() opens tel: URI when Bria is available."""
        dialer = BriaDialer()
        dialer._available = True

        with patch("src.integrations.bria.webbrowser.open") as mock_open:
            result = dialer.dial("(713) 555-1234")

        assert result is True
        mock_open.assert_called_once_with("tel:7135551234")

    def test_dial_falls_back_to_clipboard_when_unavailable(self):
        """dial() copies to clipboard when Bria is unavailable."""
        dialer = BriaDialer()
        dialer._available = False

        with patch.object(dialer, "_copy_to_clipboard", return_value=True) as mock_copy:
            result = dialer.dial("(713) 555-1234")

        assert result is False  # False = clipboard fallback
        mock_copy.assert_called_once_with("7135551234")

    def test_dial_falls_back_on_webbrowser_exception(self):
        """dial() falls back to clipboard if webbrowser.open raises."""
        dialer = BriaDialer()
        dialer._available = True

        with patch("src.integrations.bria.webbrowser.open", side_effect=OSError("fail")):
            with patch.object(dialer, "_copy_to_clipboard", return_value=True) as mock_copy:
                result = dialer.dial("713-555-1234")

        assert result is False
        mock_copy.assert_called_once_with("7135551234")

    def test_dial_invalid_number_returns_false(self):
        """dial() returns False for empty/invalid phone number."""
        dialer = BriaDialer()
        result = dialer.dial("")
        assert result is False

    def test_dial_international_number(self):
        """dial() correctly formats international numbers with + prefix."""
        dialer = BriaDialer()
        dialer._available = True

        with patch("src.integrations.bria.webbrowser.open") as mock_open:
            result = dialer.dial("+1-303-555-1234")

        assert result is True
        mock_open.assert_called_once_with("tel:+13035551234")


class TestPhoneFormatting:
    """Test phone number formatting."""

    def test_normalize_for_dial_domestic(self):
        """Normalizes domestic number."""
        dialer = BriaDialer()
        normalized = dialer._normalize_for_dial("(303) 555-1234")
        assert normalized == "3035551234"

    def test_normalize_for_dial_international(self):
        """Normalizes international number with + prefix."""
        dialer = BriaDialer()
        normalized = dialer._normalize_for_dial("+1-303-555-1234")
        assert normalized == "+13035551234"

    def test_normalize_already_clean(self):
        """Already-clean number passes through."""
        dialer = BriaDialer()
        assert dialer._normalize_for_dial("7135551234") == "7135551234"

    def test_normalize_empty_string(self):
        """Empty string returns empty string."""
        dialer = BriaDialer()
        assert dialer._normalize_for_dial("") == ""

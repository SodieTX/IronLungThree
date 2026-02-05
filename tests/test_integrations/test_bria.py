"""Tests for Bria softphone integration."""

import pytest

from src.integrations.bria import BriaDialer


class TestBriaDialer:
    """Test BriaDialer class."""

    @pytest.mark.skip(reason="Stub not implemented")
    def test_health_check(self):
        """Health check returns True when Bria available."""
        pass

    @pytest.mark.skip(reason="Stub not implemented")
    def test_dial_formats_number(self):
        """Dial formats number correctly."""
        pass


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

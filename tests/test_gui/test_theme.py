"""Tests for theme configuration."""

import pytest

try:
    from src.gui.theme import COLORS, FONTS

    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

pytestmark = pytest.mark.skipif(not HAS_TKINTER, reason="tkinter not available")


class TestColors:
    """Test color definitions."""

    def test_colors_defined(self):
        """Required colors are defined."""
        assert "bg" in COLORS
        assert "fg" in COLORS
        assert "accent" in COLORS
        assert "danger" in COLORS

    def test_colors_are_hex(self):
        """Colors are hex strings."""
        for color in COLORS.values():
            assert color.startswith("#")
            assert len(color) == 7


class TestFonts:
    """Test font definitions."""

    def test_fonts_defined(self):
        """Required fonts are defined."""
        assert "default" in FONTS
        assert "large" in FONTS
        assert "mono" in FONTS

    def test_fonts_are_tuples(self):
        """Fonts are (name, size) tuples."""
        for font in FONTS.values():
            assert isinstance(font, tuple)
            assert len(font) == 2

"""Tests for import intake funnel."""

import pytest

from src.db.intake import ImportRecord, IntakeFunnel


class TestIntakeFunnel:
    """Test IntakeFunnel class."""

    @pytest.mark.skip(reason="Stub not implemented")
    def test_analyze_new_records(self, memory_db):
        """Analyze identifies new records."""
        pass

    @pytest.mark.skip(reason="Stub not implemented")
    def test_analyze_duplicate_detection(self, memory_db):
        """Analyze detects duplicates."""
        pass

    @pytest.mark.skip(reason="Stub not implemented")
    def test_dnc_records_blocked(self, memory_db):
        """Records matching DNC are blocked."""
        pass


class TestNameSimilarity:
    """Test name similarity functions."""

    def test_exact_match(self):
        """Exact names have high similarity."""
        similarity = IntakeFunnel.name_similarity("John Smith", "John Smith")
        assert similarity >= 0.9

    def test_different_names_low_similarity(self):
        """Different names have low similarity."""
        similarity = IntakeFunnel.name_similarity("John Smith", "Jane Doe")
        assert similarity < 0.5


class TestPhoneNormalization:
    """Test phone normalization."""

    def test_normalize_with_country_code(self):
        """Keeps all digits including country code."""
        assert IntakeFunnel.normalize_phone("+1 (303) 555-1234") == "13035551234"

    def test_normalize_various_formats(self):
        """Handles various formats."""
        assert IntakeFunnel.normalize_phone("303-555-1234") == "3035551234"
        assert IntakeFunnel.normalize_phone("303.555.1234") == "3035551234"
        assert IntakeFunnel.normalize_phone("(303) 555-1234") == "3035551234"

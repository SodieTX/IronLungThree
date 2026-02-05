"""Tests for morning brief generation."""

import pytest
from src.content.morning_brief import generate_morning_brief, MorningBrief


class TestMorningBrief:
    """Test morning brief generation."""
    
    @pytest.mark.skip(reason="Stub not implemented")
    def test_generates_brief(self, memory_db):
        """Generates a morning brief."""
        brief = generate_morning_brief(memory_db)
        assert isinstance(brief, MorningBrief)
        assert brief.date is not None
    
    @pytest.mark.skip(reason="Stub not implemented")
    def test_brief_includes_pipeline_summary(self, memory_db):
        """Brief includes pipeline summary."""
        brief = generate_morning_brief(memory_db)
        assert brief.pipeline_summary != ""

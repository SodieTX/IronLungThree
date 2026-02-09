"""Tests for disposition engine."""

import pytest

from src.ai.disposition import Disposition, determine_disposition, validate_disposition
from src.db.models import Population


class TestDetermineDisposition:
    """Test disposition determination."""

    def test_determine_won(self):
        """Recognizes 'won' disposition."""
        disposition = determine_disposition("They signed the contract!")
        assert disposition.outcome == "WON"

    def test_determine_dead(self):
        """Recognizes 'dead' disposition."""
        disposition = determine_disposition("Company shut down")
        assert disposition.outcome == "OUT"
        assert disposition.reason == "company_closed"


class TestValidateDisposition:
    """Test disposition validation."""

    def test_won_requires_value(self):
        """WON disposition requires deal value."""
        disposition = Disposition(outcome="WON", deal_value=None)
        is_valid, errors = validate_disposition(disposition)
        assert not is_valid
        assert "deal_value" in str(errors)

    def test_lost_requires_reason(self):
        """LOST disposition requires reason."""
        disposition = Disposition(outcome="OUT", population=Population.LOST)
        is_valid, errors = validate_disposition(disposition)
        assert not is_valid
        assert any("reason" in e for e in errors)

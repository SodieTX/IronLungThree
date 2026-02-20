"""Tests for disposition engine."""

from datetime import date
from decimal import Decimal

import pytest

from src.ai.disposition import (
    Disposition,
    apply_disposition,
    determine_disposition,
    validate_disposition,
)
from src.db.models import LostReason, Population


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

    def test_determine_lost(self):
        """Recognizes 'lost' disposition."""
        disposition = determine_disposition("They went with competitor")
        assert disposition.outcome == "OUT"
        assert disposition.population == Population.LOST

    def test_determine_alive_default(self):
        """Defaults to ALIVE for neutral input."""
        disposition = determine_disposition("Had a good conversation")
        assert disposition.outcome == "ALIVE"

    def test_determine_from_list(self):
        """Handles list of conversation entries."""
        conversation = [
            {"content": "They are ready to sign"},
            {"content": "Contract coming Monday"},
        ]
        disposition = determine_disposition(conversation)
        assert disposition.outcome == "WON"


class TestValidateDisposition:
    """Test disposition validation."""

    def test_won_requires_value(self):
        """WON disposition requires deal value."""
        disposition = Disposition(outcome="WON", deal_value=None)
        is_valid, errors = validate_disposition(disposition)
        assert not is_valid
        assert "deal_value" in str(errors)

    def test_won_valid_with_value(self):
        """WON is valid with deal value."""
        disposition = Disposition(
            outcome="WON",
            population=Population.CLOSED_WON,
            deal_value=Decimal("5000"),
        )
        is_valid, errors = validate_disposition(disposition)
        assert is_valid

    def test_lost_requires_reason(self):
        """LOST disposition requires reason."""
        disposition = Disposition(outcome="OUT", population=Population.LOST)
        is_valid, errors = validate_disposition(disposition)
        assert not is_valid
        assert any("reason" in e for e in errors)

    def test_lost_valid_with_reason(self):
        """LOST is valid with reason."""
        disposition = Disposition(
            outcome="OUT",
            population=Population.LOST,
            reason="went_with_competitor",
        )
        is_valid, errors = validate_disposition(disposition)
        assert is_valid

    def test_alive_requires_followup(self):
        """ALIVE needs follow-up date."""
        disposition = Disposition(outcome="ALIVE")
        is_valid, errors = validate_disposition(disposition)
        assert not is_valid
        assert any("follow_up_date" in e for e in errors)

    def test_parked_requires_month(self):
        """PARKED needs parked_month."""
        disposition = Disposition(outcome="OUT", population=Population.PARKED)
        is_valid, errors = validate_disposition(disposition)
        assert not is_valid
        assert any("parked_month" in e for e in errors)


class TestApplyDisposition:
    """Test applying dispositions."""

    def test_apply_won(self, populated_db):
        """Applies WON disposition."""
        prospects = populated_db.get_prospects()
        prospect = prospects[0]

        disposition = Disposition(
            outcome="WON",
            population=Population.CLOSED_WON,
            deal_value=Decimal("10000"),
            close_notes="12-month contract",
        )
        result = apply_disposition(populated_db, prospect.id, disposition)
        assert result is True

        updated = populated_db.get_prospect(prospect.id)
        assert updated.deal_value == Decimal("10000")

    def test_apply_parked(self, populated_db):
        """Applies PARKED disposition."""
        prospects = populated_db.get_prospects()
        prospect = next(p for p in prospects if p.population == Population.UNENGAGED)

        disposition = Disposition(
            outcome="OUT",
            population=Population.PARKED,
            parked_month="2026-06",
        )
        result = apply_disposition(populated_db, prospect.id, disposition)
        assert result is True

        updated = populated_db.get_prospect(prospect.id)
        assert updated.parked_month == "2026-06"

    def test_apply_to_missing_prospect(self, populated_db):
        """Returns False for missing prospect."""
        disposition = Disposition(outcome="WON", population=Population.CLOSED_WON)
        result = apply_disposition(populated_db, 99999, disposition)
        assert result is False

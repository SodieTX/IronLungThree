"""Tests for cadence system."""

from datetime import date, datetime, timedelta

import pytest

from src.db.models import Population, Prospect
from src.engine.cadence import (
    DEFAULT_INTERVALS,
    calculate_next_contact,
    get_overdue,
    set_follow_up,
)


class TestDefaultIntervals:
    """Test default cadence intervals."""

    def test_unengaged_intervals_exist(self):
        """Unengaged intervals are defined."""
        assert len(DEFAULT_INTERVALS) > 0

    def test_first_attempt_is_shortest(self):
        """First attempt has shortest interval."""
        first = DEFAULT_INTERVALS[1].min_days
        second = DEFAULT_INTERVALS[2].min_days
        assert first <= second


class TestCalculateNextContact:
    """Test next contact calculation."""

    @pytest.mark.skip(reason="Stub not implemented")
    def test_first_attempt_calculation(self, sample_prospect: Prospect):
        """First attempt uses first interval."""
        sample_prospect.attempt_count = 0
        next_date = calculate_next_contact(sample_prospect)
        assert next_date is not None

    @pytest.mark.skip(reason="Stub not implemented")
    def test_engaged_uses_explicit_date(self, sample_engaged_prospect: Prospect):
        """Engaged prospects use explicit follow-up date."""
        pass


class TestGetOverdue:
    """Test overdue detection."""

    @pytest.mark.skip(reason="Stub not implemented")
    def test_get_overdue_returns_past_due(self, memory_db):
        """Returns prospects past follow-up date."""
        pass

"""Tests for input parser."""

from datetime import date, timedelta

import pytest

from src.ai.parser import parse, parse_population_signal, parse_relative_date
from src.db.models import Population


class TestParseRelativeDate:
    """Test relative date parsing."""

    def test_parse_tomorrow(self):
        """'tomorrow' parses to next day."""
        result = parse_relative_date("tomorrow")
        expected = date.today() + timedelta(days=1)
        assert result == expected

    def test_parse_next_week(self):
        """'next week' parses to 7 days."""
        result = parse_relative_date("next week")
        expected = date.today() + timedelta(days=7)
        assert result == expected

    def test_parse_specific_day(self):
        """'next Tuesday' parses correctly."""
        result = parse_relative_date("next Tuesday")
        assert result is not None
        assert result.weekday() == 1  # Tuesday


class TestParsePopulationSignal:
    """Test population signal detection."""

    def test_detect_dead_signal(self):
        """Detects dead signals."""
        signal = parse_population_signal("They went out of business")
        assert signal == Population.DEAD_DNC

    def test_detect_dnc_signal(self):
        """Detects DNC signals."""
        signal = parse_population_signal("Remove me from your list")
        assert signal == Population.DEAD_DNC


class TestParse:
    """Test full input parsing."""

    def test_parse_follow_up(self):
        """Parses follow-up instruction."""
        result = parse("Follow up next Tuesday at 2pm")
        assert result.action == "set_follow_up"
        assert result.date is not None

"""Tests for input parser."""

from datetime import date, timedelta

import pytest

from src.ai.parser import (
    extract_intel,
    parse,
    parse_population_signal,
    parse_relative_date,
)
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

    def test_parse_in_few_days(self):
        """'in a few days' parses to +3."""
        result = parse_relative_date("in a few days")
        expected = date.today() + timedelta(days=3)
        assert result == expected

    def test_parse_in_n_days(self):
        """'in 5 days' parses correctly."""
        result = parse_relative_date("in 5 days")
        expected = date.today() + timedelta(days=5)
        assert result == expected

    def test_parse_in_n_weeks(self):
        """'in 2 weeks' parses correctly."""
        result = parse_relative_date("in 2 weeks")
        expected = date.today() + timedelta(weeks=2)
        assert result == expected

    def test_parse_none_for_garbage(self):
        """Returns None for unparseable text."""
        result = parse_relative_date("whenever the stars align")
        assert result is None


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

    def test_detect_hard_no(self):
        """Detects 'hard no' as DNC."""
        signal = parse_population_signal("hard no")
        assert signal == Population.DEAD_DNC

    def test_detect_engaged_signal(self):
        """Detects engaged signals."""
        signal = parse_population_signal("he's interested")
        assert signal == Population.ENGAGED

    def test_detect_parked_signal(self):
        """Detects park signals."""
        signal = parse_population_signal("not now, call me later")
        assert signal == Population.PARKED

    def test_no_signal_in_neutral(self):
        """Returns None for neutral text."""
        result = parse_population_signal("Nice weather today")
        assert result is None


class TestParse:
    """Test full input parsing."""

    def test_parse_follow_up(self):
        """Parses follow-up instruction."""
        result = parse("Follow up next Tuesday at 2pm")
        assert result.action == "set_follow_up"
        assert result.date is not None

    def test_parse_lv(self):
        """'LV' means left voicemail."""
        result = parse("lv")
        assert result.action == "voicemail"
        assert result.confidence >= 0.9

    def test_parse_left_voicemail(self):
        """'left voicemail' means voicemail."""
        result = parse("left voicemail")
        assert result.action == "voicemail"

    def test_parse_no_answer(self):
        """'no answer' means call with no_answer outcome."""
        result = parse("no answer")
        assert result.action == "call"
        assert result.parameters["outcome"] == "no_answer"

    def test_parse_skip(self):
        """'skip' is navigation."""
        result = parse("skip")
        assert result.action == "skip"
        assert result.confidence == 1.0

    def test_parse_undo(self):
        """'undo' is navigation."""
        result = parse("undo")
        assert result.action == "undo"

    def test_parse_yes(self):
        """'yes' is confirmation."""
        result = parse("yes")
        assert result.action == "confirm"

    def test_parse_no(self):
        """'no' is denial."""
        result = parse("no")
        assert result.action == "deny"

    def test_parse_send_email(self):
        """'send him an email' triggers email action."""
        result = parse("send him an email")
        assert result.action == "send_email"

    def test_parse_dial(self):
        """'dial him' triggers dial action."""
        result = parse("dial him")
        assert result.action == "dial"

    def test_parse_park_with_month(self):
        """'park until March' extracts month."""
        result = parse("park until march")
        assert result.action == "park"
        assert result.parameters.get("parked_month") is not None
        assert "-03" in result.parameters["parked_month"]

    def test_parse_schedule_demo(self):
        """'schedule a demo' triggers demo action."""
        result = parse("schedule a demo")
        assert result.action == "schedule_demo"

    def test_parse_wrong_number(self):
        """'wrong number' flags suspect."""
        result = parse("wrong number")
        assert result.action == "flag_suspect"
        assert result.parameters["field"] == "phone"

    def test_parse_empty(self):
        """Empty input returns empty action."""
        result = parse("")
        assert result.action == "empty"

    def test_parse_freeform_as_note(self):
        """Unknown text defaults to note."""
        result = parse("talked about the new product launch happening next quarter")
        assert result.action == "note"
        assert result.confidence < 0.5

    def test_parse_interested(self):
        """'he's interested' triggers population change."""
        result = parse("he's interested")
        assert result.action == "population_change"
        assert result.parameters["population"] == Population.ENGAGED.value


class TestExtractIntel:
    """Test intel extraction from text."""

    def test_extracts_loan_types(self):
        """Detects loan type mentions."""
        nuggets = extract_intel("They do bridge and fix and flip lending", prospect_id=1)
        categories = [n["category"] for n in nuggets]
        assert "loan_type" in categories
        loan_nugget = next(n for n in nuggets if n["category"] == "loan_type")
        assert "bridge" in loan_nugget["content"]

    def test_extracts_pain_points(self):
        """Detects pain point patterns."""
        nuggets = extract_intel(
            "They are struggling with manual borrower intake processes every day",
            prospect_id=1,
        )
        categories = [n["category"] for n in nuggets]
        assert "pain_point" in categories

    def test_no_intel_from_simple_text(self):
        """No nuggets from simple text."""
        nuggets = extract_intel("Called him today", prospect_id=1)
        assert len(nuggets) == 0

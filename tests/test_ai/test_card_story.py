"""Tests for card story generator."""

from datetime import date, datetime

import pytest

from src.ai.card_story import (
    _describe_status,
    _extract_key_moments,
    _format_activity_date,
    _format_intel,
    _summarize_timeline,
    generate_story,
)
from src.db.models import (
    Activity,
    ActivityType,
    EngagementStage,
    IntelCategory,
    IntelNugget,
    Population,
)


class TestDescribeStatus:
    """Test status description."""

    def test_unengaged(self):
        result = _describe_status(Population.UNENGAGED, None, None)
        assert "chasing" in result.lower()

    def test_engaged_with_stage(self):
        result = _describe_status(Population.ENGAGED, EngagementStage.DEMO_SCHEDULED, None)
        assert "demo scheduled" in result.lower()

    def test_parked_with_month(self):
        result = _describe_status(Population.PARKED, None, "2026-06")
        assert "2026-06" in result

    def test_dead_dnc(self):
        result = _describe_status(Population.DEAD_DNC, None, None)
        assert "do not contact" in result.lower()

    def test_closed_won(self):
        result = _describe_status(Population.CLOSED_WON, None, None)
        assert "won" in result.lower()


class TestSummarizeTimeline:
    """Test timeline summarization."""

    def test_empty_activities(self):
        assert _summarize_timeline([]) == ""

    def test_single_activity(self):
        act = Activity(
            prospect_id=1,
            activity_type=ActivityType.CALL,
            created_at=datetime(2026, 1, 15),
        )
        result = _summarize_timeline([act])
        assert "One interaction" in result

    def test_multiple_activities(self):
        activities = [
            Activity(
                prospect_id=1,
                activity_type=ActivityType.CALL,
                created_at=datetime(2026, 2, 1),
            ),
            Activity(
                prospect_id=1,
                activity_type=ActivityType.EMAIL_SENT,
                created_at=datetime(2026, 1, 15),
            ),
        ]
        result = _summarize_timeline(activities)
        assert "2 interactions" in result


class TestExtractKeyMoments:
    """Test key moment extraction."""

    def test_status_change(self):
        act = Activity(
            prospect_id=1,
            activity_type=ActivityType.STATUS_CHANGE,
            population_before=Population.UNENGAGED,
            population_after=Population.ENGAGED,
            created_at=datetime(2026, 1, 20),
        )
        moments = _extract_key_moments([act])
        assert len(moments) == 1
        assert "unengaged" in moments[0].lower()
        assert "engaged" in moments[0].lower()

    def test_demo_completed(self):
        act = Activity(
            prospect_id=1,
            activity_type=ActivityType.DEMO_COMPLETED,
            created_at=datetime(2026, 2, 5),
        )
        moments = _extract_key_moments([act])
        assert "demo completed" in moments[0].lower()

    def test_limits_to_five(self):
        activities = [
            Activity(
                prospect_id=1,
                activity_type=ActivityType.NOTE,
                notes=f"Note number {i} with enough text to matter",
                created_at=datetime(2026, 1, i + 1),
            )
            for i in range(10)
        ]
        moments = _extract_key_moments(activities)
        assert len(moments) <= 5


class TestFormatIntel:
    """Test intel formatting."""

    def test_empty_nuggets(self):
        assert _format_intel([]) == ""

    def test_formats_nuggets(self):
        nuggets = [
            IntelNugget(
                prospect_id=1,
                category=IntelCategory.PAIN_POINT,
                content="Manual borrower intake",
            ),
            IntelNugget(
                prospect_id=1,
                category=IntelCategory.LOAN_TYPE,
                content="bridge, fix and flip",
            ),
        ]
        result = _format_intel(nuggets)
        assert "Pain Point" in result
        assert "Manual borrower intake" in result
        assert "Loan Type" in result


class TestFormatActivityDate:
    """Test date formatting."""

    def test_none(self):
        assert _format_activity_date(None) == "unknown date"

    def test_datetime(self):
        result = _format_activity_date(datetime(2026, 3, 15, 10, 0))
        assert "Mar" in result
        assert "15" in result

    def test_string(self):
        result = _format_activity_date("2026-03-15T10:00:00")
        assert "2026-03-15" in result


class TestGenerateStory:
    """Test full story generation."""

    def test_generates_story(self, populated_db):
        """Generates a story for a real prospect."""
        prospects = populated_db.get_prospects()
        assert len(prospects) > 0
        story = generate_story(populated_db, prospects[0].id)
        assert "Acme" in story

    def test_missing_prospect(self, memory_db):
        """Handles missing prospect gracefully."""
        result = generate_story(memory_db, 99999)
        assert "No prospect data" in result

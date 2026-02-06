"""Tests for AI copilot (Phase 7, Steps 7.1 + 7.2)."""

from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from src.ai.copilot import Copilot, CopilotResponse
from src.db.database import Database
from src.db.models import (
    Company,
    EngagementStage,
    Population,
    Prospect,
)


@pytest.fixture
def db():
    """Create in-memory database for testing."""
    database = Database(":memory:")
    database.initialize()
    yield database
    database.close()


@pytest.fixture
def company_id(db):
    """Create a test company."""
    company = Company(name="Demo Corp", state="TX")
    return db.create_company(company)


@pytest.fixture
def copilot(db):
    """Create copilot with mock config (no API key)."""
    with patch("src.ai.copilot.get_config") as mock_config:
        mock_config.return_value.claude_api_key = ""
        return Copilot(db)


class TestPipelineSummary:
    """Tests for pipeline summary generation."""

    def test_empty_pipeline(self, copilot):
        """Empty DB returns zero-count summary."""
        summary = copilot.pipeline_summary()
        assert "0 total prospects" in summary

    def test_pipeline_with_data(self, copilot, company_id):
        """Pipeline summary includes population counts."""
        copilot.db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Test",
                last_name="Person",
                population=Population.ENGAGED,
            )
        )
        copilot.db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Test2",
                last_name="Person2",
                population=Population.UNENGAGED,
            )
        )

        summary = copilot.pipeline_summary()
        assert "Engaged: 1" in summary
        assert "Unengaged: 1" in summary


class TestCompanyStory:
    """Tests for company story generation."""

    def test_nonexistent_company(self, copilot):
        """Nonexistent company returns error message."""
        story = copilot.company_story(999)
        assert "not found" in story.lower()

    def test_company_with_prospects(self, copilot, company_id):
        """Company story includes prospect data."""
        copilot.db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="John",
                last_name="Doe",
                population=Population.ENGAGED,
                prospect_score=85,
            )
        )

        story = copilot.company_story(company_id)
        assert "Demo Corp" in story
        assert "John Doe" in story
        assert "engaged" in story


class TestDemoBriefing:
    """Tests for demo briefing generation."""

    def test_nonexistent_prospect(self, copilot):
        """Nonexistent prospect returns error."""
        briefing = copilot.demo_briefing(999)
        assert "not found" in briefing.lower()

    def test_demo_briefing_content(self, copilot, company_id):
        """Demo briefing includes prospect info."""
        pid = copilot.db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Jane",
                last_name="Smith",
                title="VP Operations",
                population=Population.ENGAGED,
                prospect_score=90,
            )
        )

        briefing = copilot.demo_briefing(pid)
        assert "Jane Smith" in briefing
        assert "Demo Corp" in briefing
        assert "VP Operations" in briefing


class TestAsk:
    """Tests for the ask() router."""

    def test_pipeline_question(self, copilot, company_id):
        """Pipeline-related questions return pipeline summary."""
        response = copilot.ask("What's our pipeline looking like?")
        assert isinstance(response, CopilotResponse)
        assert (
            "total prospects" in response.message.lower() or "pipeline" in response.message.lower()
        )

    def test_story_question(self, copilot, company_id):
        """Story questions trigger entity lookup."""
        copilot.db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Bob",
                last_name="Builder",
                population=Population.ENGAGED,
            )
        )

        response = copilot.ask("What's the story with Demo Corp?")
        assert isinstance(response, CopilotResponse)
        assert "Demo Corp" in response.message

    def test_problems_question(self, copilot):
        """Decay/problems questions return health report."""
        response = copilot.ask("Any problems I should know about?")
        assert isinstance(response, CopilotResponse)
        # Either clean or has issues
        assert (
            "clean" in response.message.lower()
            or "issues" in response.message.lower()
            or "found" in response.message.lower()
        )

    def test_learning_question(self, copilot):
        """Win/loss pattern questions trigger learning report."""
        response = copilot.ask("What are our win patterns?")
        assert isinstance(response, CopilotResponse)

    def test_fallback_without_api(self, copilot):
        """Unknown question without API key shows help text."""
        response = copilot.ask("What is the weather going to be like?")
        assert isinstance(response, CopilotResponse)
        assert "help with" in response.message.lower() or "pipeline" in response.message.lower()


class TestRecordManipulation:
    """Tests for record manipulation via conversation (Step 7.2)."""

    def test_move_to_engaged(self, copilot, company_id):
        """'Move [name] to engaged' transitions prospect."""
        copilot.db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Alice",
                last_name="Wonderland",
                population=Population.UNENGAGED,
            )
        )

        response = copilot.ask("Move Alice Wonderland to engaged")
        assert response.action_taken is not None
        assert "engaged" in response.action_taken.lower()

    def test_move_invalid_transition(self, copilot, company_id):
        """Invalid transition returns error message."""
        copilot.db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Dead",
                last_name="Contact",
                population=Population.DEAD_DNC,
            )
        )

        response = copilot.ask("Move Dead Contact to engaged")
        assert response.action_taken is None
        # Should mention it can't be done (not found or transition error)
        assert "can't" in response.message.lower() or "no prospect" in response.message.lower()

    def test_move_unknown_prospect(self, copilot):
        """Moving nonexistent prospect returns error."""
        response = copilot.ask("Move Nonexistent Person to engaged")
        assert "no prospect" in response.message.lower()

    def test_set_followup(self, copilot, company_id):
        """'Set follow-up for [name] to tomorrow' works."""
        copilot.db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Bob",
                last_name="Followup",
                population=Population.ENGAGED,
            )
        )

        response = copilot.ask("Set follow-up for Bob Followup to tomorrow")
        assert response.action_taken is not None
        assert "follow-up" in response.action_taken.lower()

    def test_park_until_month(self, copilot, company_id):
        """'Park [name] until March' transitions to parked."""
        copilot.db.create_prospect(
            Prospect(
                company_id=company_id,
                first_name="Charlie",
                last_name="Parkable",
                population=Population.UNENGAGED,
            )
        )

        response = copilot.ask("Park Charlie Parkable until march")
        assert response.action_taken is not None
        assert "parked" in response.action_taken.lower()


class TestDateParsing:
    """Tests for date parsing utility."""

    def test_parse_iso_date(self, copilot):
        result = copilot._parse_date("2025-06-15")
        assert result is not None
        assert result.year == 2025
        assert result.month == 6
        assert result.day == 15

    def test_parse_tomorrow(self, copilot):
        result = copilot._parse_date("tomorrow")
        assert result is not None
        expected = date.today() + timedelta(days=1)
        assert result.date() == expected

    def test_parse_today(self, copilot):
        result = copilot._parse_date("today")
        assert result is not None
        assert result.date() == date.today()

    def test_parse_in_days(self, copilot):
        result = copilot._parse_date("in 5 days")
        assert result is not None
        expected = date.today() + timedelta(days=5)
        assert result.date() == expected

    def test_parse_invalid(self, copilot):
        result = copilot._parse_date("not a date")
        assert result is None


class TestMonthParsing:
    """Tests for month parsing utility."""

    def test_parse_iso_month(self, copilot):
        result = copilot._parse_month("2025-03")
        assert result == "2025-03"

    def test_parse_month_name(self, copilot):
        result = copilot._parse_month("march")
        assert result is not None
        assert result.endswith("-03")

    def test_parse_month_with_year(self, copilot):
        result = copilot._parse_month("march 2026")
        assert result == "2026-03"

    def test_parse_abbreviated_month(self, copilot):
        result = copilot._parse_month("sep")
        assert result is not None
        assert "-09" in result

    def test_parse_invalid_month(self, copilot):
        result = copilot._parse_month("not a month")
        assert result is None

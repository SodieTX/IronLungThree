"""Integration tests for Anne action execution -> DB persistence.

Verifies that execute_actions actually writes to the database,
not just returns success.
"""

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from src.ai.anne import Anne
from src.db.models import (
    ActivityType,
    ContactMethod,
    ContactMethodType,
    EngagementStage,
    Population,
)


@pytest.fixture
def anne(populated_db, monkeypatch):
    """Anne instance without API key (offline mode)."""
    monkeypatch.setattr("src.ai.anne.get_config", lambda: MagicMock(claude_api_key=None))
    return Anne(populated_db)


@pytest.fixture
def prospect_id(populated_db):
    """Return first prospect ID from the populated DB."""
    prospects = populated_db.get_prospects()
    assert len(prospects) > 0
    return prospects[0].id


class TestLogActivity:
    """Test that log_activity actions persist to DB."""

    def test_call_logged(self, anne, populated_db, prospect_id):
        actions = [
            {
                "action": "log_activity",
                "prospect_id": prospect_id,
                "type": "call",
                "outcome": "no_answer",
            }
        ]
        result = anne.execute_actions(actions)
        assert "log_activity" in result["executed"]

        # Verify DB has the activity
        activities = populated_db.get_activities(prospect_id)
        call_activities = [a for a in activities if a.activity_type == ActivityType.CALL]
        assert len(call_activities) >= 1

    def test_voicemail_logged(self, anne, populated_db, prospect_id):
        actions = [
            {
                "action": "log_activity",
                "prospect_id": prospect_id,
                "type": "voicemail",
                "outcome": "left_vm",
            }
        ]
        result = anne.execute_actions(actions)
        assert "log_activity" in result["executed"]

    def test_attempt_count_incremented(self, anne, populated_db, prospect_id):
        before = populated_db.get_prospect(prospect_id)
        before_count = before.attempt_count or 0

        actions = [
            {
                "action": "log_activity",
                "prospect_id": prospect_id,
                "type": "call",
                "outcome": "no_answer",
            }
        ]
        anne.execute_actions(actions)

        after = populated_db.get_prospect(prospect_id)
        assert after.attempt_count == before_count + 1

    def test_last_contact_date_updated(self, anne, populated_db, prospect_id):
        actions = [
            {
                "action": "log_activity",
                "prospect_id": prospect_id,
                "type": "call",
                "outcome": "no_answer",
            }
        ]
        anne.execute_actions(actions)

        after = populated_db.get_prospect(prospect_id)
        assert after.last_contact_date == date.today()


class TestLogNote:
    """Test that log_note actions persist to DB."""

    def test_note_persisted(self, anne, populated_db, prospect_id):
        actions = [
            {
                "action": "log_note",
                "prospect_id": prospect_id,
                "text": "Great conversation about fix-and-flip",
            }
        ]
        result = anne.execute_actions(actions)
        assert "log_note" in result["executed"]

        activities = populated_db.get_activities(prospect_id)
        note_activities = [a for a in activities if a.activity_type == ActivityType.NOTE]
        assert any("fix-and-flip" in (a.notes or "") for a in note_activities)


class TestPopulationChange:
    """Test population transitions via Anne."""

    def test_move_to_lost(self, anne, populated_db, prospect_id):
        actions = [
            {
                "action": "population_change",
                "prospect_id": prospect_id,
                "population": "lost",
            }
        ]
        result = anne.execute_actions(actions)
        assert "population_change" in result["executed"]

        after = populated_db.get_prospect(prospect_id)
        assert after.population == Population.LOST


class TestSetFollowUp:
    """Test follow-up date setting."""

    def test_follow_up_persisted(self, anne, populated_db, prospect_id):
        actions = [
            {
                "action": "set_follow_up",
                "prospect_id": prospect_id,
                "date": "2026-03-15",
            }
        ]
        result = anne.execute_actions(actions)
        assert "set_follow_up" in result["executed"]

        after = populated_db.get_prospect(prospect_id)
        assert after.follow_up_date is not None
        # Verify the date was set (could be date or datetime)
        fu = after.follow_up_date
        if isinstance(fu, datetime):
            assert fu.date() == date(2026, 3, 15)
        else:
            assert str(fu)[:10] == "2026-03-15"


class TestScheduleDemo:
    """Test demo scheduling."""

    def test_demo_creates_activity(self, anne, populated_db, prospect_id):
        actions = [
            {
                "action": "schedule_demo",
                "prospect_id": prospect_id,
                "date": "2026-03-20",
            }
        ]
        result = anne.execute_actions(actions)
        assert "schedule_demo" in result["executed"]

        activities = populated_db.get_activities(prospect_id)
        demo_activities = [a for a in activities if a.activity_type == ActivityType.DEMO_SCHEDULED]
        assert len(demo_activities) >= 1


class TestUnknownAction:
    """Test error handling for unknown actions."""

    def test_unknown_action_fails(self, anne):
        result = anne.execute_actions([{"action": "teleport"}])
        assert len(result["failed"]) == 1

    def test_missing_prospect_id_skipped(self, anne):
        """Actions without prospect_id should not crash."""
        result = anne.execute_actions([{"action": "log_note", "text": "orphan note"}])
        # No prospect_id, so the action returns early without error
        assert len(result["failed"]) == 0

"""Tests for troubled cards service — overdue, stalled, suspect data."""

from datetime import date, datetime, timedelta

import pytest

from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    Company,
    ContactMethod,
    ContactMethodType,
    EngagementStage,
    Population,
    Prospect,
)
from src.engine.troubled_cards import TroubledCardsService


@pytest.fixture
def troubled_db(memory_db: Database) -> Database:
    """Database with a mix of troubled and healthy prospects."""
    today = date.today()
    co_id = memory_db.create_company(Company(name="Test Corp", state="TX"))

    # OVERDUE: engaged, follow-up 5 days ago, has recent activity (so not stalled)
    p_overdue = memory_db.create_prospect(
        Prospect(
            company_id=co_id,
            first_name="Over",
            last_name="Due",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.PRE_DEMO,
            follow_up_date=datetime.combine(today - timedelta(days=5), datetime.min.time()),
        )
    )
    memory_db.create_activity(Activity(prospect_id=p_overdue, activity_type=ActivityType.CALL))

    # ON TIME: engaged, follow-up today (NOT troubled)
    p_ontime = memory_db.create_prospect(
        Prospect(
            company_id=co_id,
            first_name="On",
            last_name="Time",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.PRE_DEMO,
            follow_up_date=datetime.combine(today, datetime.min.time()),
        )
    )
    memory_db.create_activity(Activity(prospect_id=p_ontime, activity_type=ActivityType.CALL))

    # STALLED: engaged, last activity 20 days ago, no follow-up date
    p_stalled = memory_db.create_prospect(
        Prospect(
            company_id=co_id,
            first_name="Stale",
            last_name="Fish",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.POST_DEMO,
        )
    )
    # Manually insert old activity
    conn = memory_db._get_connection()
    old_date = (today - timedelta(days=20)).isoformat()
    conn.execute(
        """INSERT INTO activities (prospect_id, activity_type, created_at)
           VALUES (?, ?, ?)""",
        (p_stalled, ActivityType.CALL.value, old_date),
    )
    conn.commit()

    # SUSPECT DATA: unengaged with suspect contact method
    p_suspect = memory_db.create_prospect(
        Prospect(
            company_id=co_id,
            first_name="Bad",
            last_name="Data",
            population=Population.UNENGAGED,
            follow_up_date=datetime.combine(today + timedelta(days=5), datetime.min.time()),
        )
    )
    memory_db.create_contact_method(
        ContactMethod(
            prospect_id=p_suspect,
            type=ContactMethodType.EMAIL,
            value="bad@invalid.test",
            is_suspect=True,
        )
    )

    # HEALTHY: unengaged, future follow-up, no issues (NOT troubled)
    memory_db.create_prospect(
        Prospect(
            company_id=co_id,
            first_name="Healthy",
            last_name="Prospect",
            population=Population.UNENGAGED,
            follow_up_date=datetime.combine(today + timedelta(days=3), datetime.min.time()),
        )
    )

    return memory_db


class TestTroubledCardsService:
    def test_finds_overdue(self, troubled_db: Database) -> None:
        svc = TroubledCardsService(troubled_db)
        cards = svc.get_troubled_cards()
        overdue = [c for c in cards if c.trouble_type == "overdue"]
        assert len(overdue) >= 1
        assert any("Over Due" in c.prospect_name for c in overdue)

    def test_finds_stalled(self, troubled_db: Database) -> None:
        svc = TroubledCardsService(troubled_db)
        cards = svc.get_troubled_cards()
        stalled = [c for c in cards if c.trouble_type == "stalled"]
        assert len(stalled) >= 1
        assert any("Stale Fish" in c.prospect_name for c in stalled)

    def test_finds_suspect_data(self, troubled_db: Database) -> None:
        svc = TroubledCardsService(troubled_db)
        cards = svc.get_troubled_cards()
        suspect = [c for c in cards if c.trouble_type == "suspect_data"]
        assert len(suspect) >= 1
        assert any("Bad Data" in c.prospect_name for c in suspect)

    def test_excludes_healthy_prospects(self, troubled_db: Database) -> None:
        svc = TroubledCardsService(troubled_db)
        cards = svc.get_troubled_cards()
        names = [c.prospect_name for c in cards]
        assert "Healthy Prospect" not in names

    def test_sorted_by_severity(self, troubled_db: Database) -> None:
        svc = TroubledCardsService(troubled_db)
        cards = svc.get_troubled_cards()
        # Should be sorted by days_overdue descending
        for i in range(len(cards) - 1):
            assert cards[i].days_overdue >= cards[i + 1].days_overdue

    def test_empty_database(self, memory_db: Database) -> None:
        svc = TroubledCardsService(memory_db)
        cards = svc.get_troubled_cards()
        assert cards == []

    def test_deduplication(self, troubled_db: Database) -> None:
        svc = TroubledCardsService(troubled_db)
        cards = svc.get_troubled_cards()
        ids = [c.prospect_id for c in cards]
        assert len(ids) == len(set(ids)), "Duplicate prospect IDs in results"

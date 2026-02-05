"""Tests for rescue engine — zero-capacity crisis mode."""

from datetime import date, datetime

import pytest

from src.ai.rescue import RescueEngine, RescueItem
from src.db.database import Database
from src.db.models import Company, EngagementStage, Population, Prospect


@pytest.fixture
def rescue_db(memory_db: Database) -> Database:
    """Database with a mix of engaged and unengaged prospects."""
    today = date.today()

    co_id = memory_db.create_company(Company(name="Acme Corp", state="TX"))

    # Engaged: closing stage, due today — highest priority
    memory_db.create_prospect(
        Prospect(
            company_id=co_id,
            first_name="Alice",
            last_name="Closer",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.CLOSING,
            follow_up_date=datetime(today.year, today.month, today.day, 9, 0),
            prospect_score=95,
        )
    )

    # Engaged: post-demo, due today
    memory_db.create_prospect(
        Prospect(
            company_id=co_id,
            first_name="Bob",
            last_name="PostDemo",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.POST_DEMO,
            follow_up_date=datetime(today.year, today.month, today.day, 10, 0),
            prospect_score=80,
        )
    )

    # Engaged: demo_scheduled, due today
    memory_db.create_prospect(
        Prospect(
            company_id=co_id,
            first_name="Carol",
            last_name="Demo",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.DEMO_SCHEDULED,
            follow_up_date=datetime(today.year, today.month, today.day, 14, 0),
            prospect_score=85,
        )
    )

    # Engaged: pre-demo, due today
    memory_db.create_prospect(
        Prospect(
            company_id=co_id,
            first_name="Dave",
            last_name="PreDemo",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.PRE_DEMO,
            follow_up_date=datetime(today.year, today.month, today.day, 11, 0),
            prospect_score=70,
        )
    )

    # Unengaged: high score, due today
    memory_db.create_prospect(
        Prospect(
            company_id=co_id,
            first_name="Eve",
            last_name="Unengaged",
            population=Population.UNENGAGED,
            follow_up_date=datetime(today.year, today.month, today.day, 9, 0),
            prospect_score=90,
        )
    )

    # Unengaged: low score, due today
    memory_db.create_prospect(
        Prospect(
            company_id=co_id,
            first_name="Frank",
            last_name="LowScore",
            population=Population.UNENGAGED,
            follow_up_date=datetime(today.year, today.month, today.day, 9, 0),
            prospect_score=20,
        )
    )

    # Engaged: due tomorrow — should NOT appear
    memory_db.create_prospect(
        Prospect(
            company_id=co_id,
            first_name="Grace",
            last_name="Tomorrow",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.PRE_DEMO,
            follow_up_date=(
                datetime(today.year, today.month, today.day + 1, 9, 0)
                if today.day < 28
                else datetime(today.year, today.month + 1, 1, 9, 0)
            ),
            prospect_score=60,
        )
    )

    return memory_db


class TestRescueEngine:
    def test_generates_max_3_items(self, rescue_db: Database) -> None:
        engine = RescueEngine(rescue_db)
        items = engine.generate_rescue_list(max_items=3)
        assert len(items) == 3

    def test_engaged_closing_is_top_priority(self, rescue_db: Database) -> None:
        engine = RescueEngine(rescue_db)
        items = engine.generate_rescue_list(max_items=5)
        assert items[0].prospect_name == "Alice Closer"
        assert items[0].priority == 100

    def test_priority_order(self, rescue_db: Database) -> None:
        engine = RescueEngine(rescue_db)
        items = engine.generate_rescue_list(max_items=4)
        # Should be: Closing (100) > Post-demo (90) > Demo-scheduled (85) > Pre-demo (80)
        assert items[0].prospect_name == "Alice Closer"
        assert items[1].prospect_name == "Bob PostDemo"
        assert items[2].prospect_name == "Carol Demo"
        assert items[3].prospect_name == "Dave PreDemo"

    def test_engaged_before_unengaged(self, rescue_db: Database) -> None:
        engine = RescueEngine(rescue_db)
        items = engine.generate_rescue_list(max_items=10)
        # All engaged should come before unengaged
        engaged_names = {"Alice Closer", "Bob PostDemo", "Carol Demo", "Dave PreDemo"}
        for i, item in enumerate(items):
            if item.prospect_name not in engaged_names:
                # Once we hit an unengaged, no more engaged after
                for j in range(i + 1, len(items)):
                    assert items[j].prospect_name not in engaged_names

    def test_empty_database(self, memory_db: Database) -> None:
        engine = RescueEngine(memory_db)
        items = engine.generate_rescue_list()
        assert items == []

    def test_future_followups_excluded(self, rescue_db: Database) -> None:
        engine = RescueEngine(rescue_db)
        items = engine.generate_rescue_list(max_items=20)
        names = [i.prospect_name for i in items]
        assert "Grace Tomorrow" not in names

    def test_action_text_for_closing(self, rescue_db: Database) -> None:
        engine = RescueEngine(rescue_db)
        items = engine.generate_rescue_list(max_items=1)
        assert items[0].action == "Follow up"
        assert "closing" in items[0].reason.lower()

    def test_action_text_for_demo(self, rescue_db: Database) -> None:
        engine = RescueEngine(rescue_db)
        items = engine.generate_rescue_list(max_items=10)
        demo_item = next(i for i in items if "Carol" in i.prospect_name)
        assert demo_item.action == "Confirm demo"

    def test_custom_max_items(self, rescue_db: Database) -> None:
        engine = RescueEngine(rescue_db)
        items = engine.generate_rescue_list(max_items=1)
        assert len(items) == 1

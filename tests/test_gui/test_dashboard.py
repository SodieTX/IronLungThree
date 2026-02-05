"""Tests for glanceable dashboard — today's progress stats from DB."""

from datetime import date, datetime

import pytest

from src.db.database import Database
from src.db.models import Activity, ActivityType, Company, Population, Prospect
from src.gui.adhd.dashboard import DashboardData, DashboardService


@pytest.fixture
def dash_db(memory_db: Database) -> Database:
    """Database with activities logged today."""
    # Create a company and prospect
    company_id = memory_db.create_company(Company(name="Test Corp", state="TX"))
    prospect_id = memory_db.create_prospect(
        Prospect(company_id=company_id, first_name="John", last_name="Doe")
    )

    # Log some activities for today
    for _ in range(3):
        memory_db.create_activity(
            Activity(prospect_id=prospect_id, activity_type=ActivityType.STATUS_CHANGE)
        )
    for _ in range(2):
        memory_db.create_activity(
            Activity(prospect_id=prospect_id, activity_type=ActivityType.CALL)
        )
    memory_db.create_activity(
        Activity(prospect_id=prospect_id, activity_type=ActivityType.VOICEMAIL)
    )
    memory_db.create_activity(
        Activity(prospect_id=prospect_id, activity_type=ActivityType.EMAIL_SENT)
    )
    memory_db.create_activity(
        Activity(prospect_id=prospect_id, activity_type=ActivityType.DEMO_SCHEDULED)
    )
    memory_db.create_activity(
        Activity(prospect_id=prospect_id, activity_type=ActivityType.SKIP)
    )

    return memory_db


class TestDashboardService:
    def test_get_dashboard_data(self, dash_db: Database) -> None:
        svc = DashboardService(dash_db)
        data = svc.get_dashboard_data(
            current_streak=7,
            cards_total=20,
            target_date=date.today(),
        )
        assert isinstance(data, DashboardData)
        assert data.cards_processed == 4  # 3 status_change + 1 skip
        assert data.calls_made == 3  # 2 calls + 1 voicemail
        assert data.emails_sent == 1
        assert data.demos_scheduled == 1
        assert data.current_streak == 7
        assert data.cards_total == 20

    def test_empty_database_returns_zeros(self, memory_db: Database) -> None:
        svc = DashboardService(memory_db)
        data = svc.get_dashboard_data(target_date=date.today())
        assert data.cards_processed == 0
        assert data.calls_made == 0
        assert data.emails_sent == 0
        assert data.demos_scheduled == 0

    def test_different_date_returns_zeros(self, dash_db: Database) -> None:
        svc = DashboardService(dash_db)
        # Query a past date where no activities exist
        data = svc.get_dashboard_data(target_date=date(2025, 1, 1))
        assert data.cards_processed == 0

    def test_performance_dashboard_refresh(self, dash_db: Database) -> None:
        """Dashboard refresh should be < 50ms."""
        import time

        svc = DashboardService(dash_db)
        start = time.perf_counter()
        svc.get_dashboard_data(target_date=date.today())
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 50, f"Dashboard took {elapsed_ms:.1f}ms, expected < 50ms"

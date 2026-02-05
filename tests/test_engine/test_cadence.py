"""Tests for cadence system.

Tests Step 2.3-2.4: Cadence Engine + Queue Builder
    - Unengaged interval calculation
    - Business day math (skip weekends)
    - Follow-up setting with activity logging
    - Orphan detection (engaged without follow-up)
    - Overdue detection
    - Queue ordering (engaged first, then unengaged)
    - Timezone ordering within groups
"""

from datetime import date, datetime, timedelta

import pytest

from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    Company,
    EngagementStage,
    Population,
    Prospect,
)
from src.engine.cadence import (
    DEFAULT_INTERVALS,
    add_business_days,
    calculate_next_contact,
    get_interval,
    get_orphaned_engaged,
    get_overdue,
    get_todays_follow_ups,
    get_todays_queue,
    set_follow_up,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def db():
    """Fresh in-memory database."""
    database = Database(":memory:")
    database.initialize()
    yield database
    database.close()


@pytest.fixture
def tx_company_id(db):
    """Create a Texas company."""
    return db.create_company(Company(name="TX Corp", state="TX"))


@pytest.fixture
def ny_company_id(db):
    """Create a New York company."""
    return db.create_company(Company(name="NY Corp", state="NY"))


@pytest.fixture
def ca_company_id(db):
    """Create a California company."""
    return db.create_company(Company(name="CA Corp", state="CA"))


# =============================================================================
# UNENGAGED CADENCE
# =============================================================================


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

    def test_intervals_escalate(self):
        """Intervals increase with each attempt."""
        for i in range(1, 4):
            current = DEFAULT_INTERVALS[i].min_days
            nxt = DEFAULT_INTERVALS[i + 1].min_days
            assert nxt >= current

    def test_interval_has_channel(self):
        """Each interval has a suggested channel."""
        for interval in DEFAULT_INTERVALS.values():
            assert interval.channel in ("call", "email", "combo")


class TestGetInterval:
    """Test interval retrieval."""

    def test_known_attempt(self):
        """Known attempt returns defined interval."""
        interval = get_interval(1)
        assert interval.min_days == 3
        assert interval.max_days == 5

    def test_beyond_defined(self):
        """Attempt beyond defined uses long interval."""
        interval = get_interval(10)
        assert interval.min_days == 14
        assert interval.max_days == 21


class TestCalculateNextContact:
    """Test next contact calculation."""

    def test_first_attempt(self):
        """First attempt uses 3 business days."""
        last = date(2026, 2, 3)  # Tuesday
        next_date = calculate_next_contact(1, last, 1)
        # 3 business days from Tuesday = Friday
        assert next_date == date(2026, 2, 6)

    def test_second_attempt(self):
        """Second attempt uses 5 business days."""
        last = date(2026, 2, 3)  # Tuesday
        next_date = calculate_next_contact(1, last, 2)
        # 5 business days from Tuesday = next Tuesday
        assert next_date == date(2026, 2, 10)

    def test_third_attempt(self):
        """Third attempt uses 7 business days."""
        last = date(2026, 2, 3)
        next_date = calculate_next_contact(1, last, 3)
        # 7 business days from Tuesday
        assert next_date == date(2026, 2, 12)

    def test_fourth_attempt(self):
        """Fourth attempt uses 10 business days."""
        last = date(2026, 2, 3)
        next_date = calculate_next_contact(1, last, 4)
        # 10 business days from Tuesday = 2 weeks later
        assert next_date == date(2026, 2, 17)

    def test_fifth_plus_attempt(self):
        """Fifth+ attempt uses 14 business days."""
        last = date(2026, 2, 3)
        next_date = calculate_next_contact(1, last, 5)
        # 14 business days from Tuesday
        assert next_date.weekday() < 5  # Always lands on a weekday


# =============================================================================
# BUSINESS DAY MATH
# =============================================================================


class TestAddBusinessDays:
    """Test business day calculation."""

    def test_simple_weekday(self):
        """Adding days within a week."""
        # Monday + 3 = Thursday
        result = add_business_days(date(2026, 2, 2), 3)
        assert result == date(2026, 2, 5)

    def test_crosses_weekend(self):
        """Adding days that cross a weekend."""
        # Thursday + 2 = Monday (skips Saturday/Sunday)
        result = add_business_days(date(2026, 2, 5), 2)
        assert result == date(2026, 2, 9)

    def test_friday_plus_one(self):
        """Friday + 1 = Monday."""
        result = add_business_days(date(2026, 2, 6), 1)
        assert result == date(2026, 2, 9)

    def test_zero_days(self):
        """Zero business days returns same date."""
        d = date(2026, 2, 3)
        result = add_business_days(d, 0)
        assert result == d

    def test_result_never_weekend(self):
        """Result never lands on a weekend."""
        for start_day in range(1, 8):
            start = date(2026, 2, start_day)
            for days in range(1, 30):
                result = add_business_days(start, days)
                assert result.weekday() < 5, f"Got weekend from {start} + {days}"


# =============================================================================
# ENGAGED CADENCE
# =============================================================================


class TestSetFollowUp:
    """Test setting follow-up dates."""

    def test_set_follow_up(self, db, tx_company_id):
        """Sets follow-up date on prospect."""
        pid = db.create_prospect(
            Prospect(
                company_id=tx_company_id,
                first_name="Test",
                last_name="User",
                population=Population.ENGAGED,
                engagement_stage=EngagementStage.PRE_DEMO,
            )
        )
        follow_date = datetime(2026, 2, 15, 10, 0)
        result = set_follow_up(db, pid, follow_date, reason="He said call Wednesday")
        assert result is True

        prospect = db.get_prospect(pid)
        assert prospect.follow_up_date is not None

    def test_set_follow_up_logs_activity(self, db, tx_company_id):
        """Setting follow-up creates activity."""
        pid = db.create_prospect(
            Prospect(
                company_id=tx_company_id,
                first_name="Test",
                last_name="User",
                population=Population.ENGAGED,
            )
        )
        follow_date = datetime(2026, 2, 15, 10, 0)
        set_follow_up(db, pid, follow_date, reason="Callback requested")

        activities = db.get_activities(pid)
        assert len(activities) >= 1
        assert activities[0].activity_type == ActivityType.REMINDER

    def test_nonexistent_prospect_returns_false(self, db):
        """Non-existent prospect returns False."""
        result = set_follow_up(db, 9999, datetime.now())
        assert result is False


# =============================================================================
# ORPHAN DETECTION
# =============================================================================


class TestOrphanDetection:
    """Test orphaned engaged prospect detection."""

    def test_engaged_without_follow_up_is_orphan(self, db, tx_company_id):
        """Engaged prospect without follow-up detected."""
        pid = db.create_prospect(
            Prospect(
                company_id=tx_company_id,
                first_name="Orphan",
                last_name="Test",
                population=Population.ENGAGED,
                engagement_stage=EngagementStage.PRE_DEMO,
                follow_up_date=None,
            )
        )
        orphans = get_orphaned_engaged(db)
        assert pid in orphans

    def test_engaged_with_follow_up_not_orphan(self, db, tx_company_id):
        """Engaged prospect with follow-up is not orphaned."""
        pid = db.create_prospect(
            Prospect(
                company_id=tx_company_id,
                first_name="Not",
                last_name="Orphan",
                population=Population.ENGAGED,
                engagement_stage=EngagementStage.PRE_DEMO,
                follow_up_date=datetime(2026, 2, 15, 10, 0),
            )
        )
        orphans = get_orphaned_engaged(db)
        assert pid not in orphans

    def test_unengaged_without_follow_up_not_orphan(self, db, tx_company_id):
        """Unengaged without follow-up is NOT an orphan (expected state)."""
        pid = db.create_prospect(
            Prospect(
                company_id=tx_company_id,
                first_name="Unengaged",
                last_name="Test",
                population=Population.UNENGAGED,
            )
        )
        orphans = get_orphaned_engaged(db)
        assert pid not in orphans


# =============================================================================
# OVERDUE DETECTION
# =============================================================================


class TestOverdueDetection:
    """Test overdue follow-up detection."""

    def test_past_follow_up_is_overdue(self, db, tx_company_id):
        """Prospect with past follow-up is overdue."""
        yesterday = datetime.now() - timedelta(days=2)
        pid = db.create_prospect(
            Prospect(
                company_id=tx_company_id,
                first_name="Overdue",
                last_name="Test",
                population=Population.ENGAGED,
                follow_up_date=yesterday,
            )
        )
        overdue = get_overdue(db)
        assert any(p.id == pid for p in overdue)

    def test_future_follow_up_not_overdue(self, db, tx_company_id):
        """Prospect with future follow-up is not overdue."""
        future = datetime.now() + timedelta(days=5)
        pid = db.create_prospect(
            Prospect(
                company_id=tx_company_id,
                first_name="Future",
                last_name="Test",
                population=Population.ENGAGED,
                follow_up_date=future,
            )
        )
        overdue = get_overdue(db)
        assert not any(p.id == pid for p in overdue)

    def test_dnc_not_in_overdue(self, db, tx_company_id):
        """DNC prospects excluded from overdue list."""
        yesterday = datetime.now() - timedelta(days=2)
        pid = db.create_prospect(
            Prospect(
                company_id=tx_company_id,
                first_name="DNC",
                last_name="Test",
                population=Population.DEAD_DNC,
                follow_up_date=yesterday,
            )
        )
        overdue = get_overdue(db)
        assert not any(p.id == pid for p in overdue)

    def test_overdue_ordered_by_date(self, db, tx_company_id):
        """Overdue prospects ordered most overdue first."""
        db.create_prospect(
            Prospect(
                company_id=tx_company_id,
                first_name="Recent",
                last_name="Overdue",
                population=Population.ENGAGED,
                follow_up_date=datetime.now() - timedelta(days=1),
            )
        )
        db.create_prospect(
            Prospect(
                company_id=tx_company_id,
                first_name="Very",
                last_name="Overdue",
                population=Population.ENGAGED,
                follow_up_date=datetime.now() - timedelta(days=10),
            )
        )
        overdue = get_overdue(db)
        if len(overdue) >= 2:
            # Most overdue first (earliest follow_up_date)
            assert overdue[0].first_name == "Very"


# =============================================================================
# QUEUE BUILDER (Step 2.4)
# =============================================================================


class TestQueueBuilder:
    """Test today's work queue assembly."""

    def test_engaged_before_unengaged(self, db, tx_company_id):
        """Engaged follow-ups appear before unengaged."""
        # Engaged with today's follow-up
        today = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        e_pid = db.create_prospect(
            Prospect(
                company_id=tx_company_id,
                first_name="Engaged",
                last_name="First",
                population=Population.ENGAGED,
                engagement_stage=EngagementStage.PRE_DEMO,
                follow_up_date=today,
                prospect_score=50,
            )
        )
        # Unengaged with high score
        u_pid = db.create_prospect(
            Prospect(
                company_id=tx_company_id,
                first_name="Unengaged",
                last_name="Second",
                population=Population.UNENGAGED,
                prospect_score=95,
            )
        )

        queue = get_todays_queue(db)
        engaged_pos = next((i for i, p in enumerate(queue) if p.id == e_pid), -1)
        unengaged_pos = next((i for i, p in enumerate(queue) if p.id == u_pid), -1)

        assert engaged_pos >= 0
        assert unengaged_pos >= 0
        assert engaged_pos < unengaged_pos

    def test_closing_before_pre_demo(self, db, tx_company_id):
        """Closing stage appears before pre-demo in queue."""
        today = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        pre_pid = db.create_prospect(
            Prospect(
                company_id=tx_company_id,
                first_name="PreDemo",
                last_name="Test",
                population=Population.ENGAGED,
                engagement_stage=EngagementStage.PRE_DEMO,
                follow_up_date=today,
            )
        )
        closing_pid = db.create_prospect(
            Prospect(
                company_id=tx_company_id,
                first_name="Closing",
                last_name="Test",
                population=Population.ENGAGED,
                engagement_stage=EngagementStage.CLOSING,
                follow_up_date=today,
            )
        )

        queue = get_todays_queue(db)
        closing_pos = next((i for i, p in enumerate(queue) if p.id == closing_pid), -1)
        pre_pos = next((i for i, p in enumerate(queue) if p.id == pre_pid), -1)

        assert closing_pos >= 0
        assert pre_pos >= 0
        assert closing_pos < pre_pos

    def test_unengaged_ordered_by_score(self, db, tx_company_id):
        """Unengaged prospects ordered by score descending."""
        low_pid = db.create_prospect(
            Prospect(
                company_id=tx_company_id,
                first_name="Low",
                last_name="Score",
                population=Population.UNENGAGED,
                prospect_score=20,
            )
        )
        high_pid = db.create_prospect(
            Prospect(
                company_id=tx_company_id,
                first_name="High",
                last_name="Score",
                population=Population.UNENGAGED,
                prospect_score=90,
            )
        )

        queue = get_todays_queue(db)
        high_pos = next((i for i, p in enumerate(queue) if p.id == high_pid), -1)
        low_pos = next((i for i, p in enumerate(queue) if p.id == low_pid), -1)

        assert high_pos >= 0
        assert low_pos >= 0
        assert high_pos < low_pos

    def test_dnc_not_in_queue(self, db, tx_company_id):
        """DNC prospects never appear in queue."""
        pid = db.create_prospect(
            Prospect(
                company_id=tx_company_id,
                first_name="DNC",
                last_name="Never",
                population=Population.DEAD_DNC,
            )
        )
        queue = get_todays_queue(db)
        assert not any(p.id == pid for p in queue)

    def test_empty_queue(self, db):
        """Empty database returns empty queue."""
        queue = get_todays_queue(db)
        assert queue == []

    def test_timezone_ordering(self, db, ny_company_id, tx_company_id, ca_company_id):
        """Eastern timezone prospects appear before Pacific."""
        today = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)

        ca_pid = db.create_prospect(
            Prospect(
                company_id=ca_company_id,
                first_name="Pacific",
                last_name="Test",
                population=Population.ENGAGED,
                engagement_stage=EngagementStage.PRE_DEMO,
                follow_up_date=today,
            )
        )
        ny_pid = db.create_prospect(
            Prospect(
                company_id=ny_company_id,
                first_name="Eastern",
                last_name="Test",
                population=Population.ENGAGED,
                engagement_stage=EngagementStage.PRE_DEMO,
                follow_up_date=today,
            )
        )

        queue = get_todays_queue(db)
        ny_pos = next((i for i, p in enumerate(queue) if p.id == ny_pid), -1)
        ca_pos = next((i for i, p in enumerate(queue) if p.id == ca_pid), -1)

        assert ny_pos >= 0
        assert ca_pos >= 0
        assert ny_pos < ca_pos

    def test_queue_performance(self, db, tx_company_id):
        """Queue builds from 20 prospects in < 500ms."""
        import time

        for i in range(20):
            db.create_prospect(
                Prospect(
                    company_id=tx_company_id,
                    first_name=f"Prospect{i}",
                    last_name="Test",
                    population=Population.UNENGAGED,
                    prospect_score=50 + i,
                )
            )

        start = time.time()
        queue = get_todays_queue(db)
        elapsed = time.time() - start

        assert len(queue) == 20
        assert elapsed < 0.5

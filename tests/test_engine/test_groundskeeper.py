"""Tests for Groundskeeper database maintenance.

Tests Phase 5: Groundskeeper
    - Stale record flagging
    - Priority ordering for stale data
    - Full maintenance cycle
    - Individual freshness checks (email, phone, title, company)
"""

from datetime import date, timedelta

import pytest

from src.db.database import Database
from src.db.models import (
    Company,
    ContactMethod,
    ContactMethodType,
    Population,
    Prospect,
)
from src.engine.groundskeeper import (
    DEFAULT_THRESHOLDS,
    Groundskeeper,
    StaleRecord,
    StaleThresholds,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def memory_db():
    """In-memory database for fast tests."""
    db = Database(":memory:")
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def stale_db(memory_db):
    """Database with prospects that have stale data_freshness records.

    Creates:
        - Company "Acme Corp"
        - Prospect 1: UNENGAGED with email + phone + title, freshness verified 200 days ago
        - Prospect 2: ENGAGED with email only, freshness verified 30 days ago (fresh)
        - Prospect 3: BROKEN with phone + title, no freshness records (never verified)
    """
    company = Company(
        name="Acme Corp",
        domain="acme.com",
        state="TX",
        size="medium",
    )
    cid = memory_db.create_company(company)

    # Prospect 1: All stale (verified 200 days ago)
    p1 = Prospect(
        company_id=cid,
        first_name="Alice",
        last_name="Stale",
        title="VP of Operations",
        population=Population.UNENGAGED,
        prospect_score=80,
    )
    p1_id = memory_db.create_prospect(p1)
    memory_db.create_contact_method(
        ContactMethod(
            prospect_id=p1_id,
            type=ContactMethodType.EMAIL,
            value="alice@acme.com",
        )
    )
    memory_db.create_contact_method(
        ContactMethod(
            prospect_id=p1_id,
            type=ContactMethodType.PHONE,
            value="555-111-1111",
        )
    )
    old_date = date.today() - timedelta(days=200)
    memory_db.create_data_freshness(p1_id, "email", old_date)
    memory_db.create_data_freshness(p1_id, "phone", old_date)
    memory_db.create_data_freshness(p1_id, "title", old_date)
    memory_db.create_data_freshness(p1_id, "company", old_date)

    # Prospect 2: All fresh (verified 30 days ago)
    p2 = Prospect(
        company_id=cid,
        first_name="Bob",
        last_name="Fresh",
        title="CEO",
        population=Population.ENGAGED,
        prospect_score=90,
    )
    p2_id = memory_db.create_prospect(p2)
    memory_db.create_contact_method(
        ContactMethod(
            prospect_id=p2_id,
            type=ContactMethodType.EMAIL,
            value="bob@acme.com",
        )
    )
    fresh_date = date.today() - timedelta(days=30)
    memory_db.create_data_freshness(p2_id, "email", fresh_date)
    memory_db.create_data_freshness(p2_id, "title", fresh_date)
    memory_db.create_data_freshness(p2_id, "company", fresh_date)

    # Prospect 3: No freshness records (never verified), has phone + title
    p3 = Prospect(
        company_id=cid,
        first_name="Charlie",
        last_name="Unverified",
        title="Manager",
        population=Population.BROKEN,
        prospect_score=40,
    )
    p3_id = memory_db.create_prospect(p3)
    memory_db.create_contact_method(
        ContactMethod(
            prospect_id=p3_id,
            type=ContactMethodType.PHONE,
            value="555-333-3333",
        )
    )

    return memory_db, cid, p1_id, p2_id, p3_id


# =============================================================================
# flag_stale_records
# =============================================================================


class TestFlagStaleRecords:
    """Test stale record flagging."""

    def test_flags_stale_prospect(self, stale_db):
        """Prospect with old verified data is flagged."""
        db, cid, p1_id, p2_id, p3_id = stale_db
        keeper = Groundskeeper(db)
        flagged = keeper.flag_stale_records()

        # p1 (all stale) and p3 (never verified) should be flagged
        assert p1_id in flagged
        assert p3_id in flagged

    def test_fresh_prospect_not_flagged(self, stale_db):
        """Prospect with fresh data is NOT flagged."""
        db, cid, p1_id, p2_id, p3_id = stale_db
        keeper = Groundskeeper(db)
        flagged = keeper.flag_stale_records()

        # p2 has fresh email (30 days < 90 threshold) and fresh title/company
        assert p2_id not in flagged

    def test_empty_database(self, memory_db):
        """No prospects means no flagged records."""
        keeper = Groundskeeper(memory_db)
        flagged = keeper.flag_stale_records()
        assert flagged == []

    def test_never_verified_flagged(self, stale_db):
        """Prospect with no freshness records (never verified) is flagged."""
        db, cid, p1_id, p2_id, p3_id = stale_db
        keeper = Groundskeeper(db)
        flagged = keeper.flag_stale_records()
        assert p3_id in flagged


# =============================================================================
# get_stale_by_priority
# =============================================================================


class TestGetStaleByPriority:
    """Test priority ordering for stale data."""

    def test_higher_score_prospect_first(self, stale_db):
        """Higher prospect_score x days_stale = higher priority."""
        db, cid, p1_id, p2_id, p3_id = stale_db
        keeper = Groundskeeper(db)
        stale_records = keeper.get_stale_by_priority(limit=50)

        assert len(stale_records) >= 2

        # p1 (score=80, ~200 days stale) should rank above p3 (score=40, ~threshold+1 days)
        ids_in_order = [r.prospect_id for r in stale_records]
        assert p1_id in ids_in_order
        assert p3_id in ids_in_order
        assert ids_in_order.index(p1_id) < ids_in_order.index(p3_id)

    def test_returns_stale_record_objects(self, stale_db):
        """Returns properly formed StaleRecord objects."""
        db, cid, p1_id, p2_id, p3_id = stale_db
        keeper = Groundskeeper(db)
        stale_records = keeper.get_stale_by_priority(limit=50)

        for record in stale_records:
            assert isinstance(record, StaleRecord)
            assert record.prospect_id > 0
            assert record.prospect_name != ""
            assert record.company_name != ""
            assert len(record.stale_fields) > 0
            assert record.days_stale > 0
            assert record.priority_score > 0

    def test_limit_respected(self, stale_db):
        """Limit parameter caps the returned list."""
        db, cid, p1_id, p2_id, p3_id = stale_db
        keeper = Groundskeeper(db)
        stale_records = keeper.get_stale_by_priority(limit=1)
        assert len(stale_records) <= 1

    def test_stale_fields_populated(self, stale_db):
        """Stale fields correctly reflect which data is stale."""
        db, cid, p1_id, p2_id, p3_id = stale_db
        keeper = Groundskeeper(db)
        stale_records = keeper.get_stale_by_priority(limit=50)

        p1_record = next((r for r in stale_records if r.prospect_id == p1_id), None)
        assert p1_record is not None
        # p1 has stale email, phone, title, company (all verified 200 days ago)
        assert "email" in p1_record.stale_fields
        assert "phone" in p1_record.stale_fields
        assert "title" in p1_record.stale_fields
        assert "company" in p1_record.stale_fields


# =============================================================================
# run_maintenance
# =============================================================================


class TestRunMaintenance:
    """Test full maintenance cycle."""

    def test_returns_proper_dict(self, stale_db):
        """run_maintenance returns dict with expected keys."""
        db, cid, p1_id, p2_id, p3_id = stale_db
        keeper = Groundskeeper(db)
        result = keeper.run_maintenance()

        assert "flagged" in result
        assert "by_field" in result
        assert isinstance(result["flagged"], int)
        assert isinstance(result["by_field"], dict)
        assert result["flagged"] >= 2  # p1 and p3

    def test_by_field_counts(self, stale_db):
        """by_field dict has correct field keys."""
        db, cid, p1_id, p2_id, p3_id = stale_db
        keeper = Groundskeeper(db)
        result = keeper.run_maintenance()

        by_field = result["by_field"]
        assert "email" in by_field
        assert "phone" in by_field
        assert "title" in by_field
        assert "company" in by_field

    def test_empty_database_returns_zeros(self, memory_db):
        """Empty database returns zero counts."""
        keeper = Groundskeeper(memory_db)
        result = keeper.run_maintenance()
        assert result["flagged"] == 0
        assert result["by_field"]["email"] == 0
        assert result["by_field"]["phone"] == 0
        assert result["by_field"]["title"] == 0
        assert result["by_field"]["company"] == 0


# =============================================================================
# Individual freshness checks
# =============================================================================


class TestCheckEmailFreshness:
    """Test email freshness checking."""

    def test_fresh_email_returns_none(self, stale_db):
        """Recently verified email returns None (fresh)."""
        db, cid, p1_id, p2_id, p3_id = stale_db
        keeper = Groundskeeper(db)
        # p2 has email verified 30 days ago (< 90 day threshold)
        result = keeper._check_email_freshness(p2_id)
        assert result is None

    def test_stale_email_returns_days(self, stale_db):
        """Old verified email returns days since verification."""
        db, cid, p1_id, p2_id, p3_id = stale_db
        keeper = Groundskeeper(db)
        # p1 has email verified 200 days ago (> 90 day threshold)
        result = keeper._check_email_freshness(p1_id)
        assert result is not None
        assert result >= 200

    def test_no_email_returns_none(self, stale_db):
        """Prospect without email returns None (nothing to check)."""
        db, cid, p1_id, p2_id, p3_id = stale_db
        keeper = Groundskeeper(db)
        # p3 has no email contact method
        result = keeper._check_email_freshness(p3_id)
        assert result is None


class TestCheckPhoneFreshness:
    """Test phone freshness checking."""

    def test_stale_phone_returns_days(self, stale_db):
        """Old verified phone returns days since verification."""
        db, cid, p1_id, p2_id, p3_id = stale_db
        keeper = Groundskeeper(db)
        # p1 has phone verified 200 days ago (> 180 day threshold)
        result = keeper._check_phone_freshness(p1_id)
        assert result is not None
        assert result >= 200

    def test_no_phone_returns_none(self, stale_db):
        """Prospect without phone returns None."""
        db, cid, p1_id, p2_id, p3_id = stale_db
        keeper = Groundskeeper(db)
        # p2 has no phone contact method
        result = keeper._check_phone_freshness(p2_id)
        assert result is None

    def test_never_verified_phone_returns_threshold_plus_one(self, stale_db):
        """Phone that was never verified returns threshold + 1."""
        db, cid, p1_id, p2_id, p3_id = stale_db
        keeper = Groundskeeper(db)
        # p3 has phone but no freshness record for phone
        result = keeper._check_phone_freshness(p3_id)
        assert result is not None
        assert result == DEFAULT_THRESHOLDS.phone_days + 1


class TestCheckTitleFreshness:
    """Test title freshness checking."""

    def test_stale_title_returns_days(self, stale_db):
        """Old verified title returns days since verification."""
        db, cid, p1_id, p2_id, p3_id = stale_db
        keeper = Groundskeeper(db)
        # p1 has title verified 200 days ago (> 120 day threshold)
        result = keeper._check_title_freshness(p1_id)
        assert result is not None
        assert result >= 200

    def test_fresh_title_returns_none(self, stale_db):
        """Recently verified title returns None (fresh)."""
        db, cid, p1_id, p2_id, p3_id = stale_db
        keeper = Groundskeeper(db)
        # p2 has title verified 30 days ago (< 120 day threshold)
        result = keeper._check_title_freshness(p2_id)
        assert result is None

    def test_no_title_returns_none(self, memory_db):
        """Prospect without title returns None."""
        company = Company(name="Test", state="CA")
        cid = memory_db.create_company(company)
        p = Prospect(
            company_id=cid,
            first_name="No",
            last_name="Title",
            population=Population.UNENGAGED,
        )
        pid = memory_db.create_prospect(p)
        keeper = Groundskeeper(memory_db)
        result = keeper._check_title_freshness(pid)
        assert result is None


# =============================================================================
# Custom thresholds
# =============================================================================


class TestCustomThresholds:
    """Test custom stale thresholds."""

    def test_shorter_thresholds_flag_more(self, stale_db):
        """Shorter thresholds cause more records to be flagged."""
        db, cid, p1_id, p2_id, p3_id = stale_db

        # With very short thresholds, even p2 (verified 30 days ago) gets flagged
        short_thresholds = StaleThresholds(
            email_days=10,
            phone_days=10,
            title_days=10,
            company_days=10,
        )
        keeper = Groundskeeper(db, thresholds=short_thresholds)
        flagged = keeper.flag_stale_records()

        # p2's email was verified 30 days ago which is > 10 day threshold
        assert p2_id in flagged

    def test_longer_thresholds_flag_fewer(self, stale_db):
        """Longer thresholds cause fewer records to be flagged."""
        db, cid, p1_id, p2_id, p3_id = stale_db

        # With very long thresholds, p1 (verified 200 days ago) may still be fresh
        long_thresholds = StaleThresholds(
            email_days=365,
            phone_days=365,
            title_days=365,
            company_days=365,
        )
        keeper = Groundskeeper(db, thresholds=long_thresholds)
        flagged = keeper.flag_stale_records()

        # p1 was verified 200 days ago, which is < 365 -- not stale for field checks
        # But p1's fields are verified, so they are fresh under long thresholds
        assert p1_id not in flagged

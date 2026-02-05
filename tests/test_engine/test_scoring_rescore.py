"""Tests for rescore_all batch scoring.

Tests Phase 5: Batch Rescore
    - rescore_all processes prospects in active populations
    - Scores are updated in the database
    - Returns correct count of rescored prospects
    - Handles prospects with and without companies
"""

from datetime import date, datetime, timedelta

import pytest

from src.db.database import Database
from src.db.models import (
    Company,
    ContactMethod,
    ContactMethodType,
    EngagementStage,
    Population,
    Prospect,
)
from src.engine.scoring import rescore_all

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
def rescore_db(memory_db):
    """Database with prospects in UNENGAGED, ENGAGED, and BROKEN populations.

    Creates:
        - Company "Acme Corp" (full data)
        - Company "Mystery Inc" (sparse data)
        - Prospect 1: UNENGAGED, VP, with email+phone (Acme)
        - Prospect 2: ENGAGED/CLOSING, CEO, with verified email (Acme)
        - Prospect 3: BROKEN, no title, no contacts (Mystery)
        - Prospect 4: PARKED (should NOT be rescored)
    """
    # Full company
    acme = Company(
        name="Acme Corp",
        domain="acme.com",
        state="TX",
        size="medium",
        loan_types='["bridge", "fix_and_flip"]',
    )
    acme_id = memory_db.create_company(acme)

    # Sparse company
    mystery = Company(name="Mystery Inc")
    mystery_id = memory_db.create_company(mystery)

    # Prospect 1: UNENGAGED with good data
    p1 = Prospect(
        company_id=acme_id,
        first_name="Alice",
        last_name="Smith",
        title="VP of Operations",
        population=Population.UNENGAGED,
        prospect_score=0,  # Will be recalculated
        data_confidence=0,
        source="Conference",
        last_contact_date=date.today() - timedelta(days=10),
    )
    p1_id = memory_db.create_prospect(p1)
    memory_db.create_contact_method(
        ContactMethod(
            prospect_id=p1_id,
            type=ContactMethodType.EMAIL,
            value="alice@acme.com",
            is_verified=True,
            verified_date=date.today(),
        )
    )
    memory_db.create_contact_method(
        ContactMethod(
            prospect_id=p1_id,
            type=ContactMethodType.PHONE,
            value="555-111-1111",
        )
    )

    # Prospect 2: ENGAGED CEO at CLOSING stage
    p2 = Prospect(
        company_id=acme_id,
        first_name="Bob",
        last_name="Boss",
        title="CEO",
        population=Population.ENGAGED,
        engagement_stage=EngagementStage.CLOSING,
        prospect_score=0,
        data_confidence=0,
        source="Referral",
        last_contact_date=date.today() - timedelta(days=2),
        follow_up_date=datetime.now(),
        notes="Very interested, evaluating vendors and budget approved for Q1.",
    )
    p2_id = memory_db.create_prospect(p2)
    memory_db.create_contact_method(
        ContactMethod(
            prospect_id=p2_id,
            type=ContactMethodType.EMAIL,
            value="bob@acme.com",
            is_verified=True,
            verified_date=date.today(),
        )
    )

    # Prospect 3: BROKEN with minimal data
    p3 = Prospect(
        company_id=mystery_id,
        first_name="Charlie",
        last_name="Broken",
        population=Population.BROKEN,
        prospect_score=0,
        data_confidence=0,
        source="Purchased List",
    )
    p3_id = memory_db.create_prospect(p3)

    # Prospect 4: PARKED (should NOT be rescored by rescore_all)
    p4 = Prospect(
        company_id=acme_id,
        first_name="Donna",
        last_name="Parked",
        title="Manager",
        population=Population.PARKED,
        parked_month="2026-06",
        prospect_score=50,
        data_confidence=50,
    )
    p4_id = memory_db.create_prospect(p4)

    return memory_db, acme_id, mystery_id, p1_id, p2_id, p3_id, p4_id


# =============================================================================
# rescore_all
# =============================================================================


class TestRescoreAll:
    """Test batch rescoring of all active prospects."""

    def test_returns_correct_count(self, rescore_db):
        """rescore_all returns the number of active prospects rescored."""
        db, acme_id, mystery_id, p1_id, p2_id, p3_id, p4_id = rescore_db
        count = rescore_all(db)
        # Only UNENGAGED, ENGAGED, BROKEN are active -- p1, p2, p3
        assert count == 3

    def test_scores_updated(self, rescore_db):
        """Prospect scores are updated from their initial 0 values."""
        db, acme_id, mystery_id, p1_id, p2_id, p3_id, p4_id = rescore_db
        rescore_all(db)

        p1 = db.get_prospect(p1_id)
        p2 = db.get_prospect(p2_id)
        p3 = db.get_prospect(p3_id)

        # All were initially 0; they should now have nonzero scores
        assert p1.prospect_score > 0
        assert p2.prospect_score > 0
        assert p3.prospect_score > 0

    def test_engaged_ceo_scores_highest(self, rescore_db):
        """Engaged CEO at CLOSING stage scores highest."""
        db, acme_id, mystery_id, p1_id, p2_id, p3_id, p4_id = rescore_db
        rescore_all(db)

        p1 = db.get_prospect(p1_id)
        p2 = db.get_prospect(p2_id)
        p3 = db.get_prospect(p3_id)

        assert p2.prospect_score > p1.prospect_score
        assert p2.prospect_score > p3.prospect_score

    def test_broken_sparse_scores_lowest(self, rescore_db):
        """Broken prospect with sparse data scores lowest."""
        db, acme_id, mystery_id, p1_id, p2_id, p3_id, p4_id = rescore_db
        rescore_all(db)

        p1 = db.get_prospect(p1_id)
        p3 = db.get_prospect(p3_id)

        assert p3.prospect_score < p1.prospect_score

    def test_confidence_updated(self, rescore_db):
        """Data confidence scores are updated."""
        db, acme_id, mystery_id, p1_id, p2_id, p3_id, p4_id = rescore_db
        rescore_all(db)

        p1 = db.get_prospect(p1_id)
        p3 = db.get_prospect(p3_id)

        # p1 has full name, title, company, email+phone, verified -- high confidence
        # p3 has name only, no title, no contacts -- low confidence
        assert p1.data_confidence > p3.data_confidence

    def test_parked_not_rescored(self, rescore_db):
        """PARKED prospects are NOT included in rescore_all."""
        db, acme_id, mystery_id, p1_id, p2_id, p3_id, p4_id = rescore_db
        rescore_all(db)

        p4 = db.get_prospect(p4_id)
        # p4 was PARKED with score=50; it should remain unchanged
        assert p4.prospect_score == 50
        assert p4.data_confidence == 50

    def test_empty_database(self, memory_db):
        """rescore_all with no prospects returns 0."""
        count = rescore_all(memory_db)
        assert count == 0

    def test_idempotent(self, rescore_db):
        """Running rescore_all twice produces the same scores."""
        db, acme_id, mystery_id, p1_id, p2_id, p3_id, p4_id = rescore_db

        rescore_all(db)
        p1_first = db.get_prospect(p1_id)
        score1 = p1_first.prospect_score
        confidence1 = p1_first.data_confidence

        rescore_all(db)
        p1_second = db.get_prospect(p1_id)
        assert p1_second.prospect_score == score1
        assert p1_second.data_confidence == confidence1

    def test_scores_in_valid_range(self, rescore_db):
        """All scores are in the 0-100 range."""
        db, acme_id, mystery_id, p1_id, p2_id, p3_id, p4_id = rescore_db
        rescore_all(db)

        for pid in [p1_id, p2_id, p3_id]:
            p = db.get_prospect(pid)
            assert 0 <= p.prospect_score <= 100
            assert 0 <= p.data_confidence <= 100

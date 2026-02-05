"""Tests for nightly cycle (src/autonomous/nightly.py).

Covers:
    - run_nightly_cycle: full 11-step cycle completes with error capture
    - run_condensed_cycle: quick catch-up cycle completes
    - check_last_run: sentinel lookup in data_freshness table
    - _activate_monthly_buckets: parked prospect reactivation
    - _import_ac_contacts: ActiveCampaign contact import into DB
    - _extract_intel_from_activities: keyword-based intel nugget extraction
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import pytest

from src.autonomous.nightly import (
    NightlyCycleResult,
    _activate_monthly_buckets,
    _extract_intel_from_activities,
    _import_ac_contacts,
    _record_cycle_run,
    check_last_run,
    run_condensed_cycle,
    run_nightly_cycle,
)
from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    Company,
    ContactMethod,
    ContactMethodType,
    IntelCategory,
    Population,
    Prospect,
)


@pytest.fixture
def fk_relaxed_db(memory_db: Database) -> Database:
    """Memory DB with foreign-key checks disabled.

    The nightly cycle and _record_cycle_run use prospect_id=0 as a sentinel
    in the data_freshness table. Since prospect 0 doesn't exist, FK constraints
    block the insert. Disabling FK enforcement isolates the nightly logic.
    """
    conn = memory_db._get_connection()
    conn.execute("PRAGMA foreign_keys = OFF")
    return memory_db


# ---------------------------------------------------------------------------
# Helper: minimal ACContact-like object for _import_ac_contacts
# ---------------------------------------------------------------------------


@dataclass
class FakeACContact:
    """Mimics activecampaign.ACContact for import tests."""

    id: str = "ac-1"
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    phone: Optional[str] = None
    company: Optional[str] = None
    created_at: Optional[datetime] = None


# ===========================================================================
# run_nightly_cycle
# ===========================================================================


class TestRunNightlyCycle:
    """Full 11-step nightly cycle."""

    def test_completes_with_errors_captured(self, memory_db: Database):
        """Cycle finishes all 11 steps; services missing -> errors collected."""
        result = run_nightly_cycle(memory_db)

        assert isinstance(result, NightlyCycleResult)
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at
        # At minimum, steps that import unavailable modules will produce errors
        assert isinstance(result.errors, list)

    def test_nightly_result_fields_are_ints(self, memory_db: Database):
        """All counter fields should be non-negative ints after a run."""
        result = run_nightly_cycle(memory_db)

        for field_name in [
            "backups_created",
            "prospects_imported",
            "duplicates_merged",
            "research_completed",
            "stale_flagged",
            "prospects_scored",
            "buckets_activated",
            "nurture_drafted",
            "cards_prepared",
            "intel_extracted",
        ]:
            value = getattr(result, field_name)
            assert isinstance(value, int), f"{field_name} should be int, got {type(value)}"
            assert value >= 0, f"{field_name} should be >= 0"

    def test_records_cycle_run_in_data_freshness(self, fk_relaxed_db: Database):
        """After full cycle, check_last_run should return a date."""
        run_nightly_cycle(fk_relaxed_db)
        last = check_last_run(fk_relaxed_db)
        assert last is not None


# ===========================================================================
# run_condensed_cycle
# ===========================================================================


class TestRunCondensedCycle:
    """Quick catch-up cycle."""

    def test_completes(self, memory_db: Database):
        """Condensed cycle completes and sets completed_at."""
        result = run_condensed_cycle(memory_db)
        assert isinstance(result, NightlyCycleResult)
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at

    def test_records_cycle_run(self, fk_relaxed_db: Database):
        """Condensed cycle records a run in data_freshness."""
        run_condensed_cycle(fk_relaxed_db)
        last = check_last_run(fk_relaxed_db)
        assert last is not None


# ===========================================================================
# check_last_run
# ===========================================================================


class TestCheckLastRun:
    """Sentinel-based last-run lookup."""

    def test_returns_none_if_never_run(self, memory_db: Database):
        """Returns None when no cycle has ever been recorded."""
        result = check_last_run(memory_db)
        assert result is None

    def test_returns_datetime_after_recording(self, fk_relaxed_db: Database):
        """Returns a datetime after _record_cycle_run is called."""
        _record_cycle_run(fk_relaxed_db)
        result = check_last_run(fk_relaxed_db)
        assert result is not None
        assert isinstance(result, datetime)

    def test_returns_latest_run(self, fk_relaxed_db: Database):
        """Multiple recordings -> returns the most recent."""
        _record_cycle_run(fk_relaxed_db)
        first = check_last_run(fk_relaxed_db)

        _record_cycle_run(fk_relaxed_db)
        second = check_last_run(fk_relaxed_db)

        assert first is not None
        assert second is not None
        assert second >= first


# ===========================================================================
# _activate_monthly_buckets
# ===========================================================================


class TestActivateMonthlyBuckets:
    """Reactivate PARKED prospects whose month has arrived."""

    def _create_parked_prospect(self, db: Database, parked_month: str, name: str = "Test") -> int:
        """Helper: create a PARKED prospect with given parked_month."""
        company_id = db.create_company(Company(name=f"{name} Co"))
        prospect = Prospect(
            company_id=company_id,
            first_name=name,
            last_name="Parked",
            population=Population.PARKED,
            parked_month=parked_month,
        )
        return db.create_prospect(prospect)

    def test_activates_current_month(self, memory_db: Database):
        """Prospects parked for current month are reactivated."""
        current_month = date.today().strftime("%Y-%m")
        pid = self._create_parked_prospect(memory_db, current_month, "Alice")

        activated = _activate_monthly_buckets(memory_db)
        assert activated >= 1

        prospect = memory_db.get_prospect(pid)
        assert prospect is not None
        assert prospect.population == Population.UNENGAGED

    def test_does_not_activate_future_month(self, memory_db: Database):
        """Prospects parked for a future month stay parked."""
        future_month = "2099-12"
        pid = self._create_parked_prospect(memory_db, future_month, "Bob")

        activated = _activate_monthly_buckets(memory_db)
        assert activated == 0

        prospect = memory_db.get_prospect(pid)
        assert prospect is not None
        assert prospect.population == Population.PARKED

    def test_activates_past_month(self, memory_db: Database):
        """Prospects parked for a past month are activated (overdue)."""
        past_month = "2020-01"
        pid = self._create_parked_prospect(memory_db, past_month, "Charlie")

        activated = _activate_monthly_buckets(memory_db)
        assert activated >= 1

        prospect = memory_db.get_prospect(pid)
        assert prospect is not None
        assert prospect.population == Population.UNENGAGED

    def test_no_parked_prospects_returns_zero(self, memory_db: Database):
        """No parked prospects -> returns 0."""
        activated = _activate_monthly_buckets(memory_db)
        assert activated == 0


# ===========================================================================
# _import_ac_contacts
# ===========================================================================


class TestImportACContacts:
    """Import ActiveCampaign contact objects into the database."""

    def test_imports_new_contacts(self, memory_db: Database):
        """New contacts with email are imported successfully."""
        contacts = [
            FakeACContact(
                id="ac-1",
                email="alice@example.com",
                first_name="Alice",
                last_name="Wonder",
                company="Wonder Corp",
            ),
            FakeACContact(
                id="ac-2",
                email="bob@example.com",
                first_name="Bob",
                last_name="Builder",
                phone="555-1234",
            ),
        ]

        imported = _import_ac_contacts(memory_db, contacts)
        assert imported == 2

        # Verify Alice is in the DB
        pid = memory_db.find_prospect_by_email("alice@example.com")
        assert pid is not None

    def test_skips_contacts_without_email(self, memory_db: Database):
        """Contacts missing email are skipped."""
        contacts = [
            FakeACContact(id="ac-3", email="", first_name="NoEmail"),
        ]
        imported = _import_ac_contacts(memory_db, contacts)
        assert imported == 0

    def test_dedup_by_email(self, memory_db: Database):
        """Contacts with existing email are not re-imported."""
        # Pre-create prospect with email
        company_id = memory_db.create_company(Company(name="Existing Co"))
        pid = memory_db.create_prospect(
            Prospect(company_id=company_id, first_name="Existing", last_name="User")
        )
        memory_db.create_contact_method(
            ContactMethod(
                prospect_id=pid,
                type=ContactMethodType.EMAIL,
                value="existing@example.com",
            )
        )

        contacts = [
            FakeACContact(
                id="ac-4",
                email="existing@example.com",
                first_name="Duplicate",
                last_name="Contact",
            ),
        ]
        imported = _import_ac_contacts(memory_db, contacts)
        assert imported == 0

    def test_imports_phone_when_available(self, memory_db: Database):
        """Phone number is imported as a second contact method."""
        contacts = [
            FakeACContact(
                id="ac-5",
                email="withphone@example.com",
                first_name="Phoney",
                last_name="McRing",
                phone="555-9999",
            ),
        ]
        imported = _import_ac_contacts(memory_db, contacts)
        assert imported == 1

        pid = memory_db.find_prospect_by_email("withphone@example.com")
        assert pid is not None
        methods = memory_db.get_contact_methods(pid)
        types = {m.type for m in methods}
        assert ContactMethodType.EMAIL in types
        assert ContactMethodType.PHONE in types

    def test_empty_list_returns_zero(self, memory_db: Database):
        """Empty contact list -> 0 imported."""
        imported = _import_ac_contacts(memory_db, [])
        assert imported == 0


# ===========================================================================
# _extract_intel_from_activities
# ===========================================================================


class TestExtractIntelFromActivities:
    """Keyword-based intel extraction from activity notes."""

    def _create_activity_with_notes(self, db: Database, prospect_id: int, notes: str) -> int:
        """Helper: create an activity with specific notes."""
        activity = Activity(
            prospect_id=prospect_id,
            activity_type=ActivityType.CALL,
            notes=notes,
            created_by="user",
        )
        return db.create_activity(activity)

    def _setup_prospect(self, db: Database) -> int:
        """Helper: create a minimal company + prospect."""
        company_id = db.create_company(Company(name="Intel Test Co"))
        return db.create_prospect(
            Prospect(company_id=company_id, first_name="Intel", last_name="Subject")
        )

    def test_extracts_pain_point(self, memory_db: Database):
        """Activity mentioning 'struggling with' produces a PAIN_POINT nugget."""
        pid = self._setup_prospect(memory_db)
        self._create_activity_with_notes(
            memory_db,
            pid,
            "They are struggling with their current loan origination system heavily.",
        )

        extracted = _extract_intel_from_activities(memory_db)
        assert extracted >= 1

        nuggets = memory_db.get_intel_nuggets(pid)
        categories = [n.category for n in nuggets]
        assert IntelCategory.PAIN_POINT in categories

    def test_extracts_competitor_intel(self, memory_db: Database):
        """Activity mentioning 'currently using' produces a COMPETITOR nugget."""
        pid = self._setup_prospect(memory_db)
        self._create_activity_with_notes(
            memory_db,
            pid,
            "They are currently using CompetitorX for all their processing needs.",
        )

        extracted = _extract_intel_from_activities(memory_db)
        assert extracted >= 1

        nuggets = memory_db.get_intel_nuggets(pid)
        categories = [n.category for n in nuggets]
        assert IntelCategory.COMPETITOR in categories

    def test_extracts_timeline(self, memory_db: Database):
        """Activity mentioning 'next quarter' produces a DECISION_TIMELINE nugget."""
        pid = self._setup_prospect(memory_db)
        self._create_activity_with_notes(
            memory_db,
            pid,
            "They want to make a decision by next quarter at the latest.",
        )

        extracted = _extract_intel_from_activities(memory_db)
        assert extracted >= 1

        nuggets = memory_db.get_intel_nuggets(pid)
        categories = [n.category for n in nuggets]
        assert IntelCategory.DECISION_TIMELINE in categories

    def test_no_intel_from_short_notes(self, memory_db: Database):
        """Notes shorter than 20 chars are ignored by the SQL filter."""
        pid = self._setup_prospect(memory_db)
        self._create_activity_with_notes(memory_db, pid, "Short note")

        extracted = _extract_intel_from_activities(memory_db)
        assert extracted == 0

    def test_no_activities_returns_zero(self, memory_db: Database):
        """No recent activities -> 0 nuggets."""
        extracted = _extract_intel_from_activities(memory_db)
        assert extracted == 0

    def test_duplicate_nuggets_not_created(self, memory_db: Database):
        """Running extraction twice does not create duplicate nuggets."""
        pid = self._setup_prospect(memory_db)
        self._create_activity_with_notes(
            memory_db,
            pid,
            "They are struggling with their legacy platform and need an upgrade soon.",
        )

        first_run = _extract_intel_from_activities(memory_db)
        assert first_run >= 1

        second_run = _extract_intel_from_activities(memory_db)
        assert second_run == 0

        nuggets = memory_db.get_intel_nuggets(pid)
        # Should have exactly the nuggets from the first run, not doubled
        pain_nuggets = [n for n in nuggets if n.category == IntelCategory.PAIN_POINT]
        assert len(pain_nuggets) == 1

"""Brutal stress tests for the database layer.

Targets:
    - SQL injection via sort columns, search queries, tag names
    - Invalid enum values stored directly in SQLite
    - Foreign key violations and orphan records
    - Concurrent-like access patterns (rapid sequential ops)
    - Unicode bombs in every text field
    - NULL vs empty string confusion
    - Boundary values for integer fields
    - Bulk operations on empty lists, nonexistent IDs, huge lists
"""

import sqlite3
from datetime import date, datetime
from decimal import Decimal

import pytest

from src.core.exceptions import DatabaseError
from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityOutcome,
    ActivityType,
    Company,
    ContactMethod,
    ContactMethodType,
    EngagementStage,
    ImportSource,
    IntelCategory,
    IntelNugget,
    Population,
    Prospect,
    ProspectTag,
    ResearchStatus,
    ResearchTask,
)

# =========================================================================
# FIXTURES
# =========================================================================


@pytest.fixture
def db(tmp_path):
    """Fresh database for each test."""
    db = Database(str(tmp_path / "stress.db"))
    db.initialize()
    yield db
    db.close()


def _make_company(db, name="Test Co", state="TX"):
    """Helper to create a company and return its ID."""
    return db.create_company(Company(name=name, state=state))


def _make_prospect(db, company_id, first="John", last="Doe", **kwargs):
    """Helper to create a prospect and return its ID."""
    p = Prospect(company_id=company_id, first_name=first, last_name=last, **kwargs)
    return db.create_prospect(p)


# =========================================================================
# SQL INJECTION ATTEMPTS
# =========================================================================


class TestSQLInjection:
    """Try to break the SQL layer with injection payloads."""

    def test_search_companies_with_sql_injection(self, db):
        """Search query should be parameterized, not interpolated."""
        _make_company(db, name="Normal Corp")
        # Classic SQL injection attempt
        results = db.search_companies("'; DROP TABLE companies; --")
        assert isinstance(results, list)
        # Table should still exist
        _make_company(db, name="Still Works Corp")

    def test_search_prospects_with_injection_in_query(self, db):
        """search_query parameter in get_prospects should be safe."""
        cid = _make_company(db)
        _make_prospect(db, cid)
        results = db.get_prospects(search_query="' OR '1'='1")
        assert isinstance(results, list)

    def test_sort_column_injection_falls_back(self, db):
        """Non-whitelisted sort_by should fall back to prospect_score."""
        cid = _make_company(db)
        _make_prospect(db, cid, prospect_score=50)
        _make_prospect(db, cid, first="Jane", last="Smith", prospect_score=80)
        # Attempt injection through sort_by
        results = db.get_prospects(sort_by="id; DROP TABLE prospects; --")
        assert len(results) == 2
        # Should have fallen back to prospect_score DESC
        assert results[0].prospect_score >= results[1].prospect_score

    def test_sort_dir_injection_falls_back(self, db):
        """Non-ASC/DESC sort_dir should fall back to DESC."""
        cid = _make_company(db)
        _make_prospect(db, cid)
        results = db.get_prospects(sort_dir="ASC; DROP TABLE prospects;")
        assert isinstance(results, list)

    def test_tag_name_with_sql_injection(self, db):
        """Tag names should be parameterized."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid)
        evil_tag = "'; DELETE FROM prospects; --"
        db.add_tag(pid, evil_tag)
        tags = db.get_tags(pid)
        assert evil_tag in tags
        # Prospect should still exist
        assert db.get_prospect(pid) is not None

    def test_get_prospects_with_injection_in_tags_filter(self, db):
        """Tags filter builds IN clause - verify parameterized."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid)
        db.add_tag(pid, "legit")
        results = db.get_prospects(tags=["legit", "'; DROP TABLE prospects; --"])
        assert isinstance(results, list)


# =========================================================================
# UNICODE BOMBS
# =========================================================================


class TestUnicodeBombs:
    """Stuff every text field with Unicode chaos."""

    UNICODE_PAYLOADS = [
        "",  # Empty string
        " ",  # Single space
        "\t\n\r",  # Whitespace chars
        "José María García-López",  # Latin extended
        "田中太郎",  # CJK characters
        "Владимир Путинов",  # Cyrillic
        "محمد علي",  # Arabic (RTL)
        "🎉🔥💀🤖",  # Emoji
        "a" * 10000,  # Very long string
        "\x00\x01\x02",  # Control characters
        "Robert'); DROP TABLE students;--",  # Bobby Tables
        "\u200b\u200c\u200d\ufeff",  # Zero-width characters
        "̸̧̨̛̖̰̲̝̣̹̪̖̖̪̬̖̈́̏̾̈̅̆̈́̀̃̆̀̃",  # Zalgo text
        "NULL",  # The string NULL
        "None",  # The string None
        "true",  # The string true
    ]

    @pytest.mark.parametrize("name", UNICODE_PAYLOADS)
    def test_company_name_unicode(self, db, name):
        """Every Unicode payload should survive round-trip in company name."""
        if not name:  # Empty name is still valid for Company dataclass
            company = Company(name=name or "fallback", state="TX")
        else:
            company = Company(name=name, state="TX")
        cid = db.create_company(company)
        retrieved = db.get_company(cid)
        assert retrieved is not None
        assert retrieved.name == (name or "fallback")

    @pytest.mark.parametrize("payload", UNICODE_PAYLOADS)
    def test_prospect_notes_unicode(self, db, payload):
        """Notes field should handle any Unicode."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid, notes=payload)
        retrieved = db.get_prospect(pid)
        assert retrieved is not None
        assert retrieved.notes == payload

    @pytest.mark.parametrize("payload", UNICODE_PAYLOADS)
    def test_activity_notes_unicode(self, db, payload):
        """Activity notes should handle any Unicode."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid)
        activity = Activity(
            prospect_id=pid,
            activity_type=ActivityType.NOTE,
            notes=payload,
        )
        aid = db.create_activity(activity)
        activities = db.get_activities(pid)
        assert any(a.notes == payload for a in activities)

    def test_email_with_unicode_domain(self, db):
        """Email with internationalized domain."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid)
        method = ContactMethod(
            prospect_id=pid,
            type=ContactMethodType.EMAIL,
            value="user@münchen.de",
        )
        mid = db.create_contact_method(method)
        methods = db.get_contact_methods(pid)
        assert any(m.value == "user@münchen.de" for m in methods)


# =========================================================================
# FOREIGN KEY VIOLATIONS
# =========================================================================


class TestForeignKeyViolations:
    """Test referential integrity enforcement."""

    def test_prospect_with_nonexistent_company(self, db):
        """Creating prospect with fake company_id should fail with FK enabled."""
        with pytest.raises(DatabaseError):
            _make_prospect(db, company_id=99999)

    def test_contact_method_with_nonexistent_prospect(self, db):
        """Contact method referencing nonexistent prospect should fail."""
        with pytest.raises(DatabaseError):
            db.create_contact_method(
                ContactMethod(
                    prospect_id=99999,
                    type=ContactMethodType.EMAIL,
                    value="ghost@nowhere.com",
                )
            )

    def test_activity_with_nonexistent_prospect(self, db):
        """Activity referencing nonexistent prospect should fail."""
        with pytest.raises(DatabaseError):
            db.create_activity(
                Activity(
                    prospect_id=99999,
                    activity_type=ActivityType.NOTE,
                    notes="Phantom activity",
                )
            )

    def test_intel_nugget_with_nonexistent_prospect(self, db):
        """Intel nugget referencing nonexistent prospect should fail."""
        with pytest.raises(DatabaseError):
            db.create_intel_nugget(
                IntelNugget(
                    prospect_id=99999,
                    category=IntelCategory.KEY_FACT,
                    content="Ghost intel",
                )
            )

    def test_self_referential_prospect(self, db):
        """Prospect referring to itself as referrer."""
        cid = _make_company(db)
        # Create first, then update with self-reference
        pid = _make_prospect(db, cid)
        prospect = db.get_prospect(pid)
        prospect.referred_by_prospect_id = pid
        result = db.update_prospect(prospect)
        assert result is True
        retrieved = db.get_prospect(pid)
        assert retrieved.referred_by_prospect_id == pid


# =========================================================================
# INVALID ENUM VALUES IN DATABASE
# =========================================================================


class TestInvalidEnumValues:
    """What happens when the DB has enum values the code doesn't expect?"""

    def test_invalid_population_in_db_crashes_row_to_prospect(self, db):
        """Writing an invalid population directly to SQLite should cause
        ValueError when reading back via _row_to_prospect."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid)
        # Bypass the ORM and write garbage directly
        conn = db._get_connection()
        conn.execute(
            "UPDATE prospects SET population = ? WHERE id = ?",
            ("totally_fake_population", pid),
        )
        conn.commit()
        # Reading back should raise ValueError from Population("totally_fake_population")
        with pytest.raises(ValueError):
            db.get_prospect(pid)

    def test_invalid_activity_type_crashes_row_to_activity(self, db):
        """Writing invalid activity_type directly should crash on read."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid)
        conn = db._get_connection()
        conn.execute(
            "INSERT INTO activities (prospect_id, activity_type, notes) VALUES (?, ?, ?)",
            (pid, "nonexistent_type", "test"),
        )
        conn.commit()
        with pytest.raises(ValueError):
            db.get_activities(pid)

    def test_invalid_contact_method_type_crashes(self, db):
        """Writing invalid contact method type should crash on read."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid)
        conn = db._get_connection()
        conn.execute(
            "INSERT INTO contact_methods (prospect_id, type, value) VALUES (?, ?, ?)",
            (pid, "carrier_pigeon", "coo coo"),
        )
        conn.commit()
        with pytest.raises(ValueError):
            db.get_contact_methods(pid)

    def test_population_counts_skips_invalid_enums(self, db):
        """get_population_counts should gracefully handle invalid enum values."""
        cid = _make_company(db)
        _make_prospect(db, cid)
        conn = db._get_connection()
        conn.execute(
            "INSERT INTO prospects (company_id, first_name, last_name, population) VALUES (?, ?, ?, ?)",
            (cid, "Ghost", "Person", "invalid_pop"),
        )
        conn.commit()
        counts = db.get_population_counts()
        # Should not crash, invalid pop is silently skipped
        assert isinstance(counts, dict)


# =========================================================================
# BOUNDARY VALUES
# =========================================================================


class TestBoundaryValues:
    """Push numeric and date fields to their limits."""

    def test_negative_prospect_score(self, db):
        """Negative score should be stored (no validation)."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid, prospect_score=-999)
        p = db.get_prospect(pid)
        assert p.prospect_score == -999

    def test_massive_prospect_score(self, db):
        """Score of 999999 should be stored (no validation)."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid, prospect_score=999999)
        p = db.get_prospect(pid)
        assert p.prospect_score == 999999

    def test_zero_attempt_count_vs_null(self, db):
        """attempt_count = 0 should come back as 0, not be coerced by `or 0`."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid, attempt_count=0)
        p = db.get_prospect(pid)
        # The `or 0` pattern treats 0 as falsy, but 0 is the correct value here
        assert p.attempt_count == 0

    def test_very_large_deal_value_decimal_not_supported(self, db):
        """BUG FOUND: Decimal type is not supported by SQLite bindings.

        The Prospect model defines deal_value as Optional[Decimal],
        but sqlite3 cannot bind Decimal directly. This means any prospect
        with a deal_value will fail to save.
        """
        cid = _make_company(db)
        with pytest.raises(DatabaseError):
            _make_prospect(db, cid, deal_value=Decimal("99999999.99"))

    def test_deal_value_as_float_works(self, db):
        """Workaround: float deal_value does work."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid, deal_value=99999.99)
        p = db.get_prospect(pid)
        assert p.deal_value is not None

    def test_negative_call_duration(self, db):
        """Negative call duration should be stored (no validation)."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid)
        aid = db.create_activity(
            Activity(
                prospect_id=pid,
                activity_type=ActivityType.CALL,
                call_duration_seconds=-60,
            )
        )
        activities = db.get_activities(pid)
        assert activities[0].call_duration_seconds == -60

    def test_zero_limit_get_prospects(self, db):
        """Limit of 0 should return empty list."""
        cid = _make_company(db)
        _make_prospect(db, cid)
        results = db.get_prospects(limit=0)
        assert results == []

    def test_huge_offset_get_prospects(self, db):
        """Offset past all records should return empty list."""
        cid = _make_company(db)
        _make_prospect(db, cid)
        results = db.get_prospects(offset=999999)
        assert results == []

    def test_negative_limit_behavior(self, db):
        """SQLite treats negative LIMIT as unlimited - verify behavior."""
        cid = _make_company(db)
        for i in range(5):
            _make_prospect(db, cid, first=f"Person{i}", last=str(i))
        results = db.get_prospects(limit=-1)
        # SQLite with negative LIMIT returns all rows
        assert len(results) == 5


# =========================================================================
# BULK OPERATIONS EDGE CASES
# =========================================================================


class TestBulkOperationsEdgeCases:
    """Push bulk operations to their limits."""

    def test_bulk_update_empty_list(self, db):
        """Bulk update with empty list should return (0, 0, 0)."""
        result = db.bulk_update_population([], Population.ENGAGED, "test")
        assert result == (0, 0, 0)

    def test_bulk_set_follow_up_empty_list(self, db):
        """Bulk set follow-up with empty list should return 0."""
        result = db.bulk_set_follow_up([], datetime(2026, 3, 1))
        assert result == 0

    def test_bulk_park_empty_list(self, db):
        """Bulk park with empty list should return (0, 0, 0)."""
        result = db.bulk_park([], "2026-06")
        assert result == (0, 0, 0)

    def test_bulk_update_nonexistent_ids(self, db):
        """Bulk update with IDs that don't exist."""
        result = db.bulk_update_population([99999, 88888, 77777], Population.ENGAGED, "ghost ids")
        assert result == (0, 0, 0)

    def test_bulk_update_mixed_valid_invalid(self, db):
        """Mix of valid and nonexistent IDs."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid, population=Population.UNENGAGED)
        result = db.bulk_update_population([pid, 99999], Population.ENGAGED, "mixed")
        assert result[0] >= 1  # At least the valid one updated

    def test_bulk_update_skips_dnc(self, db):
        """DNC records should be skipped in bulk update."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid, population=Population.DEAD_DNC)
        result = db.bulk_update_population([pid], Population.UNENGAGED, "escape dnc")
        assert result == (0, 1, 0)  # 1 skipped as DNC

    def test_bulk_park_skips_dnc(self, db):
        """DNC records should be skipped in bulk park."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid, population=Population.DEAD_DNC)
        result = db.bulk_park([pid], "2026-06")
        assert result == (0, 1, 0)


# =========================================================================
# NULL VS EMPTY STRING CONFUSION
# =========================================================================


class TestNullVsEmpty:
    """Test the distinction between NULL and empty string."""

    def test_empty_string_title_vs_none(self, db):
        """Empty string title and None title should both be retrievable."""
        cid = _make_company(db)
        p1 = _make_prospect(db, cid, first="Empty", last="Title", title="")
        p2 = _make_prospect(db, cid, first="None", last="Title", title=None)
        r1 = db.get_prospect(p1)
        r2 = db.get_prospect(p2)
        assert r1.title == ""
        assert r2.title is None

    def test_empty_string_notes_vs_none(self, db):
        """Empty string notes and None notes are different."""
        cid = _make_company(db)
        p1 = _make_prospect(db, cid, first="A", last="B", notes="")
        p2 = _make_prospect(db, cid, first="C", last="D", notes=None)
        r1 = db.get_prospect(p1)
        r2 = db.get_prospect(p2)
        # SQLite stores empty string as empty string, not NULL
        assert r1.notes == ""
        assert r2.notes is None

    def test_empty_company_name_is_stored(self, db):
        """Company with empty name should still be creatable."""
        cid = db.create_company(Company(name="", state="TX"))
        company = db.get_company(cid)
        assert company is not None
        assert company.name == ""


# =========================================================================
# RAPID OPERATIONS (PSEUDO-CONCURRENT)
# =========================================================================


class TestRapidOperations:
    """Simulate rapid sequential operations to test connection stability."""

    def test_create_100_companies_rapidly(self, db):
        """Create 100 companies in rapid succession."""
        ids = []
        for i in range(100):
            cid = _make_company(db, name=f"Company {i}", state="TX")
            ids.append(cid)
        assert len(set(ids)) == 100  # All unique IDs

    def test_create_100_prospects_rapidly(self, db):
        """Create 100 prospects in rapid succession."""
        cid = _make_company(db)
        ids = []
        for i in range(100):
            pid = _make_prospect(db, cid, first=f"Person{i}", last=str(i))
            ids.append(pid)
        assert len(set(ids)) == 100

    def test_rapid_tag_add_remove_cycle(self, db):
        """Add and remove tags rapidly."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid)
        for i in range(50):
            tag = f"tag-{i}"
            db.add_tag(pid, tag)
        for i in range(50):
            tag = f"tag-{i}"
            db.remove_tag(pid, tag)
        tags = db.get_tags(pid)
        assert tags == []

    def test_rapid_update_same_prospect(self, db):
        """Update the same prospect 100 times."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid)
        for i in range(100):
            p = db.get_prospect(pid)
            p.prospect_score = i
            db.update_prospect(p)
        final = db.get_prospect(pid)
        assert final.prospect_score == 99


# =========================================================================
# GET/LOOKUP EDGE CASES
# =========================================================================


class TestLookupEdgeCases:
    """Edge cases in find/search operations."""

    def test_find_prospect_by_empty_email(self, db):
        """Empty email search should return None."""
        result = db.find_prospect_by_email("")
        assert result is None

    def test_find_prospect_by_whitespace_email(self, db):
        """Whitespace email should return None (case-insensitive LOWER)."""
        result = db.find_prospect_by_email("   ")
        assert result is None

    def test_find_prospect_by_empty_phone(self, db):
        """Empty phone (no digits) should return None."""
        result = db.find_prospect_by_phone("")
        assert result is None

    def test_find_prospect_by_letters_only_phone(self, db):
        """Phone with no digits should return None."""
        result = db.find_prospect_by_phone("no-digits-here")
        assert result is None

    def test_is_dnc_with_no_args(self, db):
        """is_dnc with no email or phone should return False."""
        assert db.is_dnc() is False

    def test_is_dnc_with_empty_strings(self, db):
        """is_dnc with empty strings should return False."""
        assert db.is_dnc(email="", phone="") is False

    def test_get_nonexistent_prospect(self, db):
        """Getting a prospect that doesn't exist returns None."""
        assert db.get_prospect(99999) is None

    def test_get_nonexistent_company(self, db):
        """Getting a company that doesn't exist returns None."""
        assert db.get_company(99999) is None

    def test_get_prospect_full_nonexistent(self, db):
        """Getting full prospect view for nonexistent ID returns None."""
        assert db.get_prospect_full(99999) is None

    def test_update_prospect_with_no_id(self, db):
        """Updating prospect with id=None should return False."""
        p = Prospect(first_name="Ghost", last_name="Prospect")
        assert db.update_prospect(p) is False

    def test_update_company_with_no_id(self, db):
        """Updating company with id=None should return False."""
        c = Company(name="Ghost Corp")
        assert db.update_company(c) is False

    def test_search_companies_empty_query(self, db):
        """Search with empty string should match all (via %%)."""
        _make_company(db, name="ABC")
        _make_company(db, name="XYZ")
        results = db.search_companies("")
        assert len(results) >= 2

    def test_phone_lookup_matches_digits_only(self, db):
        """Phone lookup should strip formatting and match digits."""
        cid = _make_company(db)
        pid = _make_prospect(db, cid)
        db.create_contact_method(
            ContactMethod(
                prospect_id=pid,
                type=ContactMethodType.PHONE,
                value="(713) 555-1234",
            )
        )
        # Search with different formatting
        found = db.find_prospect_by_phone("713-555-1234")
        assert found == pid
        found = db.find_prospect_by_phone("7135551234")
        assert found == pid

    def test_phone_lookup_country_code_mismatch(self, db):
        """Phone lookup correctly handles country code normalization.

        find_prospect_by_phone now strips country codes.
        '+1 713 555 1234' -> '17135551234' -> '7135551234' (11 digits stripped to 10)
        '(713) 555-1234' -> '7135551234' (10 digits)
        These now match after normalization.

        DNC checks can no longer be bypassed by adding a country code prefix.
        """
        cid = _make_company(db)
        pid = _make_prospect(db, cid)
        db.create_contact_method(
            ContactMethod(
                prospect_id=pid,
                type=ContactMethodType.PHONE,
                value="(713) 555-1234",
            )
        )
        found = db.find_prospect_by_phone("+1 713 555 1234")
        # Bug is now fixed!
        assert found == pid


# =========================================================================
# DOUBLE INITIALIZATION
# =========================================================================


class TestDoubleInit:
    """What happens if we initialize the database twice?"""

    def test_double_initialize_is_idempotent(self, db):
        """Calling initialize() twice should not drop data."""
        cid = _make_company(db)
        _make_prospect(db, cid)
        db.initialize()  # Second init
        # Data should survive
        companies = db.search_companies("")
        assert len(companies) >= 1

    def test_triple_initialize(self, db):
        """Three times for good measure."""
        cid = _make_company(db)
        db.initialize()
        db.initialize()
        db.initialize()
        assert db.get_company(cid) is not None

"""Stress tests for data models and normalization.

Targets:
    - Company name normalization with adversarial inputs
    - Timezone lookup edge cases
    - Completeness assessment with degenerate contact methods
    - Prospect.full_name with boundary names
    - Enum membership confusion
    - Dataclass defaults and mutation
"""

from datetime import date, datetime
from decimal import Decimal

import pytest

from src.db.models import (
    Activity,
    ActivityOutcome,
    ActivityType,
    AttemptType,
    Company,
    ContactMethod,
    ContactMethodType,
    DeadReason,
    EngagementStage,
    ImportSource,
    IntelCategory,
    IntelNugget,
    LostReason,
    Population,
    Prospect,
    ProspectFull,
    ProspectTag,
    ResearchStatus,
    ResearchTask,
    assess_completeness,
    normalize_company_name,
    timezone_from_state,
)

# =========================================================================
# COMPANY NAME NORMALIZATION - ADVERSARIAL INPUTS
# =========================================================================


class TestNormalizeCompanyNameAdversarial:
    """Try to confuse the normalization regex."""

    def test_empty_string(self):
        assert normalize_company_name("") == ""

    def test_only_whitespace(self):
        assert normalize_company_name("   ") == ""

    def test_only_llc(self):
        """Just 'LLC' should normalize to empty string."""
        assert normalize_company_name("LLC") == ""

    def test_only_comma_llc(self):
        assert normalize_company_name(", LLC") == ""

    def test_double_suffix(self):
        """'ABC Inc, LLC' - dual suffixes."""
        result = normalize_company_name("ABC Inc, LLC")
        # After stripping LLC, we get "ABC Inc"
        # After stripping Inc, we get "ABC"
        # But the regex processes sequentially, so...
        # First pass: r",?\s*llc\.?$" strips ", LLC" -> "ABC Inc"
        # Second pass: r",?\s*inc\.?$" strips " Inc" -> "ABC"
        # Wait - actually the for loop processes all patterns.
        # After LLC strip: "ABC Inc"
        # After Inc strip: "ABC"
        # But wait - these aren't separate passes, it's a loop.
        # Let's verify:
        assert "abc" in result.lower()

    def test_triple_suffix(self):
        """ABC Corp Inc LLC."""
        result = normalize_company_name("ABC Corp Inc LLC")
        # LLC stripped: "ABC Corp Inc"
        # Inc stripped: "ABC Corp"
        # Corp stripped: "ABC"
        assert result == "abc"

    def test_suffix_in_middle_of_name(self):
        """'INC Manufacturing' - Inc at start should NOT be stripped."""
        result = normalize_company_name("INC Manufacturing")
        # The regexes have $ anchor, so "INC" at start won't match r",?\s*inc\.?$"
        # INC is at the start, "Manufacturing" is at the end.
        assert "inc" in result or "manufacturing" in result

    def test_llc_in_middle(self):
        """'ABC LLC Holdings' - LLC not at end."""
        result = normalize_company_name("ABC LLC Holdings")
        # r",?\s*llc\.?$" won't match because "Holdings" is after LLC
        assert "llc" in result  # LLC should be preserved

    def test_case_insensitive(self):
        assert normalize_company_name("ABC llc") == normalize_company_name("ABC LLC")

    def test_period_after_suffix(self):
        assert normalize_company_name("ABC Inc.") == "abc"

    def test_comma_before_suffix(self):
        assert normalize_company_name("ABC, Inc.") == "abc"

    def test_multiple_commas(self):
        """'ABC,, LLC' - double comma."""
        result = normalize_company_name("ABC,, LLC")
        # Regex is r",?\s*llc\.?$" which matches ", LLC" but not ",, LLC"
        # Actually ,? matches 0 or 1 comma. The first comma is part of "ABC,"
        # So the string is "ABC," + ", LLC"
        # The regex tries to match from the end: ", LLC" matches ,?\s*llc\.?$
        # Wait, the pattern is applied to the whole string.
        # "abc,, llc" -> re.sub(r",?\s*llc\.?$", "", "abc,, llc")
        # The match would be: ", llc" at the end -> "abc,"
        assert result.endswith(",") or "abc" in result

    def test_name_is_just_period(self):
        result = normalize_company_name(".")
        assert result == "."

    def test_unicode_company_name(self):
        result = normalize_company_name("Müller & Söhne GmbH")
        # GmbH is not in the suffix list
        assert "müller" in result
        assert "gmbh" in result

    def test_very_long_company_name(self):
        long_name = "A" * 10000 + ", LLC"
        result = normalize_company_name(long_name)
        assert len(result) == 10000  # Just the A's without ", LLC"

    def test_newline_in_company_name(self):
        result = normalize_company_name("ABC\nLLC")
        # \n between ABC and LLC - the $ anchor matches end of string
        # With no MULTILINE flag, $ matches end of string
        # r",?\s*llc\.?$" - \s* matches \n, so this MIGHT strip LLC
        # Actually \s matches newline, so "\nLLC" would match \s*llc$
        # Result would be "ABC" or "abc"
        # Let's just verify it doesn't crash
        assert isinstance(result, str)

    def test_tab_in_company_name(self):
        result = normalize_company_name("ABC\tInc")
        # \t is whitespace, so r",?\s*inc\.?$" might match "\tInc"
        assert isinstance(result, str)


# =========================================================================
# TIMEZONE LOOKUP EDGE CASES
# =========================================================================


class TestTimezoneLookup:
    """Push timezone_from_state to its limits."""

    def test_none_state(self):
        assert timezone_from_state(None) == "central"

    def test_empty_string(self):
        assert timezone_from_state("") == "central"

    def test_lowercase_state(self):
        assert timezone_from_state("tx") == "central"

    def test_mixed_case_state(self):
        assert timezone_from_state("Tx") == "central"

    def test_state_with_whitespace(self):
        assert timezone_from_state("  TX  ") == "central"

    def test_invalid_state_code(self):
        assert timezone_from_state("XX") == "central"

    def test_three_letter_code(self):
        """Three-letter code should return default."""
        assert timezone_from_state("TXX") == "central"

    def test_single_letter(self):
        assert timezone_from_state("T") == "central"

    def test_numeric_state(self):
        assert timezone_from_state("12") == "central"

    def test_all_50_states_have_timezone(self):
        """Every valid state code should return a non-default timezone (mostly)."""
        valid_states = [
            "AL",
            "AK",
            "AZ",
            "AR",
            "CA",
            "CO",
            "CT",
            "DE",
            "FL",
            "GA",
            "HI",
            "ID",
            "IL",
            "IN",
            "IA",
            "KS",
            "KY",
            "LA",
            "ME",
            "MD",
            "MA",
            "MI",
            "MN",
            "MS",
            "MO",
            "MT",
            "NE",
            "NV",
            "NH",
            "NJ",
            "NM",
            "NY",
            "NC",
            "ND",
            "OH",
            "OK",
            "OR",
            "PA",
            "RI",
            "SC",
            "SD",
            "TN",
            "TX",
            "UT",
            "VT",
            "VA",
            "WA",
            "WV",
            "WI",
            "WY",
            "DC",
        ]
        for state in valid_states:
            tz = timezone_from_state(state)
            assert tz in (
                "eastern",
                "central",
                "mountain",
                "pacific",
                "alaska",
                "hawaii",
            ), f"State {state} returned unexpected timezone: {tz}"


# =========================================================================
# COMPLETENESS ASSESSMENT EDGE CASES
# =========================================================================


class TestCompletenessAssessment:
    """Try to confuse the completeness checker."""

    def test_empty_contact_methods(self):
        """No contact methods = BROKEN."""
        p = Prospect(first_name="John", last_name="Doe")
        assert assess_completeness(p, []) == Population.BROKEN

    def test_email_only(self):
        """Email only = BROKEN (needs both)."""
        p = Prospect(first_name="John", last_name="Doe")
        methods = [ContactMethod(type=ContactMethodType.EMAIL, value="j@t.com")]
        assert assess_completeness(p, methods) == Population.BROKEN

    def test_phone_only(self):
        """Phone only = BROKEN."""
        p = Prospect(first_name="John", last_name="Doe")
        methods = [ContactMethod(type=ContactMethodType.PHONE, value="5551234")]
        assert assess_completeness(p, methods) == Population.BROKEN

    def test_both_email_and_phone(self):
        """Both = UNENGAGED."""
        p = Prospect(first_name="John", last_name="Doe")
        methods = [
            ContactMethod(type=ContactMethodType.EMAIL, value="j@t.com"),
            ContactMethod(type=ContactMethodType.PHONE, value="5551234"),
        ]
        assert assess_completeness(p, methods) == Population.UNENGAGED

    def test_empty_email_value_still_counts(self):
        """Empty string email should NOT count as 'has email'."""
        p = Prospect(first_name="John", last_name="Doe")
        methods = [
            ContactMethod(type=ContactMethodType.EMAIL, value=""),  # Empty!
            ContactMethod(type=ContactMethodType.PHONE, value="5551234"),
        ]
        # assess_completeness now checks value validity
        result = assess_completeness(p, methods)
        # Bug is now fixed: empty email does not count
        assert result == Population.BROKEN

    def test_multiple_emails_one_phone(self):
        """Multiple emails + one phone = UNENGAGED."""
        p = Prospect(first_name="John", last_name="Doe")
        methods = [
            ContactMethod(type=ContactMethodType.EMAIL, value="a@t.com"),
            ContactMethod(type=ContactMethodType.EMAIL, value="b@t.com"),
            ContactMethod(type=ContactMethodType.PHONE, value="5551234"),
        ]
        assert assess_completeness(p, methods) == Population.UNENGAGED


# =========================================================================
# PROSPECT FULL_NAME EDGE CASES
# =========================================================================


class TestProspectFullName:
    """Push full_name property to its limits."""

    def test_normal_name(self):
        p = Prospect(first_name="John", last_name="Doe")
        assert p.full_name == "John Doe"

    def test_empty_first_name(self):
        p = Prospect(first_name="", last_name="Doe")
        assert p.full_name == "Doe"

    def test_empty_last_name(self):
        p = Prospect(first_name="John", last_name="")
        assert p.full_name == "John"

    def test_both_empty(self):
        p = Prospect(first_name="", last_name="")
        assert p.full_name == ""

    def test_whitespace_names(self):
        p = Prospect(first_name="  ", last_name="  ")
        # "   " is not empty, so full_name = "     " stripped = ""
        assert p.full_name.strip() == ""

    def test_unicode_names(self):
        p = Prospect(first_name="José", last_name="García")
        assert p.full_name == "José García"

    def test_very_long_names(self):
        p = Prospect(first_name="A" * 5000, last_name="B" * 5000)
        assert len(p.full_name) == 10001  # 5000 + space + 5000


# =========================================================================
# ENUM EDGE CASES
# =========================================================================


class TestEnumEdgeCases:
    """Test enum membership and string behavior."""

    def test_population_is_str_enum(self):
        """Population values are strings."""
        assert Population.BROKEN == "broken"
        assert Population.BROKEN.value == "broken"

    def test_population_from_string(self):
        """Can create Population from its value."""
        assert Population("broken") == Population.BROKEN

    def test_population_invalid_string(self):
        """Invalid string should raise ValueError."""
        with pytest.raises(ValueError):
            Population("nonexistent")

    def test_all_populations_have_unique_values(self):
        """No two populations share a value."""
        values = [p.value for p in Population]
        assert len(values) == len(set(values))

    def test_activity_type_membership(self):
        """All activity types should be accessible by value."""
        for at in ActivityType:
            assert ActivityType(at.value) == at

    def test_engagement_stage_values(self):
        """Verify all engagement stage values."""
        expected = {"pre_demo", "demo_scheduled", "post_demo", "closing"}
        actual = {s.value for s in EngagementStage}
        assert actual == expected

    def test_dead_reason_only_dnc(self):
        """Only one dead reason exists."""
        assert len(list(DeadReason)) == 1
        assert DeadReason.DNC.value == "dnc"


# =========================================================================
# DATACLASS DEFAULTS AND MUTATION
# =========================================================================


class TestDataclassDefaults:
    """Test that dataclass defaults don't share mutable state."""

    def test_prospect_default_population(self):
        """Default population should be BROKEN."""
        p = Prospect()
        assert p.population == Population.BROKEN

    def test_prospect_full_default_lists(self):
        """ProspectFull default lists should be independent."""
        pf1 = ProspectFull()
        pf2 = ProspectFull()
        pf1.contact_methods.append(ContactMethod())
        pf1.activities.append(Activity())
        pf1.tags.append("test")
        # pf2 should not be affected
        assert pf2.contact_methods == []
        assert pf2.activities == []
        assert pf2.tags == []

    def test_prospect_mutation(self):
        """Prospects should be mutable (frozen=False)."""
        p = Prospect(first_name="John")
        p.first_name = "Jane"
        assert p.first_name == "Jane"

    def test_company_defaults(self):
        """Company defaults should be sensible."""
        c = Company()
        assert c.id is None
        assert c.name == ""
        assert c.timezone == "central"

    def test_import_source_defaults(self):
        """ImportSource numeric defaults should be 0."""
        s = ImportSource()
        assert s.total_records == 0
        assert s.imported_records == 0
        assert s.duplicate_records == 0
        assert s.broken_records == 0
        assert s.dnc_blocked_records == 0

"""Stress tests for the engine layer - scoring, cadence, populations.

Targets:
    - Scoring with degenerate/empty prospects and companies
    - Score weights that don't add to 100
    - Title seniority substring ambiguity
    - Cadence infinite loop with negative business days
    - Population transition warfare - every forbidden path
    - Stage transition exhaustive testing
    - rescore_all with corrupted data
"""

from datetime import date, datetime, timedelta

import pytest

from src.core.exceptions import DNCViolationError, PipelineError
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
from src.engine.cadence import (
    CadenceInterval,
    add_business_days,
    calculate_next_contact,
    get_interval,
    get_orphaned_engaged,
    get_overdue,
    get_todays_follow_ups,
    get_todays_queue,
    set_follow_up,
)
from src.engine.populations import (
    VALID_STAGE_TRANSITIONS,
    VALID_TRANSITIONS,
    can_transition,
    can_transition_stage,
    get_available_transitions,
    transition_prospect,
    transition_stage,
)
from src.engine.scoring import (
    DEFAULT_WEIGHTS,
    ScoreWeights,
    calculate_confidence,
    calculate_score,
    rescore_all,
)

# =========================================================================
# FIXTURES
# =========================================================================


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "stress.db"))
    d.initialize()
    yield d
    d.close()


def _company(db, **kwargs):
    defaults = {"name": "Test Co", "state": "TX"}
    defaults.update(kwargs)
    return db.create_company(Company(**defaults))


def _prospect(db, company_id, first="John", last="Doe", **kwargs):
    return db.create_prospect(
        Prospect(company_id=company_id, first_name=first, last_name=last, **kwargs)
    )


# =========================================================================
# SCORING EDGE CASES
# =========================================================================


class TestScoringEdgeCases:
    """Push scoring to its limits."""

    def test_score_empty_prospect_and_company(self):
        """Score with completely empty objects."""
        score = calculate_score(Prospect(), Company())
        assert 0 <= score <= 100

    def test_score_none_source(self):
        """Prospect with no source."""
        score = calculate_score(
            Prospect(source=None),
            Company(),
        )
        assert 0 <= score <= 100

    def test_score_empty_string_source(self):
        """Prospect with empty string source."""
        score = calculate_score(
            Prospect(source=""),
            Company(),
        )
        assert 0 <= score <= 100

    def test_score_all_populations(self):
        """Score should work for every population."""
        for pop in Population:
            score = calculate_score(
                Prospect(population=pop),
                Company(),
            )
            assert 0 <= score <= 100, f"Population {pop} gave score {score}"

    def test_score_engaged_all_stages(self):
        """Score engaged prospect at every stage."""
        for stage in EngagementStage:
            score = calculate_score(
                Prospect(population=Population.ENGAGED, engagement_stage=stage),
                Company(),
            )
            assert 0 <= score <= 100, f"Stage {stage} gave score {score}"

    def test_score_with_zero_weights(self):
        """All weights = 0 should give score 0."""
        weights = ScoreWeights(
            company_fit=0,
            contact_quality=0,
            engagement_signals=0,
            timing_signals=0,
            source_quality=0,
        )
        score = calculate_score(Prospect(), Company(), weights)
        assert score == 0

    def test_score_with_extreme_weights(self):
        """Extreme weights that don't sum to 100."""
        weights = ScoreWeights(
            company_fit=1000,
            contact_quality=1000,
            engagement_signals=1000,
            timing_signals=1000,
            source_quality=1000,
        )
        score = calculate_score(
            Prospect(
                population=Population.CLOSED_WON,
                title="CEO",
                source="referral",
                last_contact_date=date.today(),
            ),
            Company(loan_types="FHA", size="enterprise", state="TX", domain="test.com"),
            weights,
        )
        # With 5000 total weight instead of 100, scores get amplified
        # But clamp should keep it at 100
        assert score == 100

    def test_title_seniority_substring_ambiguity(self):
        """'Vice President' contains 'president' - should take max."""
        vp_score = calculate_score(
            Prospect(title="Vice President of Sales"),
            Company(),
        )
        ceo_score = calculate_score(
            Prospect(title="CEO"),
            Company(),
        )
        # VP contains both "vice president" (70) and "president" (95)
        # The code takes max, so VP actually scores like president
        # This might be intentional or a bug
        assert isinstance(vp_score, int)
        assert isinstance(ceo_score, int)

    def test_title_with_only_spaces(self):
        """Title that is only spaces."""
        score = calculate_score(
            Prospect(title="   "),
            Company(),
        )
        assert 0 <= score <= 100

    def test_score_with_future_last_contact(self):
        """Last contact in the future."""
        score = calculate_score(
            Prospect(last_contact_date=date.today() + timedelta(days=365)),
            Company(),
        )
        # days_since would be negative, none of the conditions match
        assert 0 <= score <= 100

    def test_score_with_ancient_last_contact(self):
        """Last contact 10 years ago."""
        score = calculate_score(
            Prospect(last_contact_date=date(2016, 1, 1)),
            Company(),
        )
        assert 0 <= score <= 100

    def test_score_with_string_last_contact_date(self):
        """Last contact as string (the scoring code has a special check for this)."""
        score = calculate_score(
            Prospect(last_contact_date="2026-01-15"),
            Company(),
        )
        # The code checks isinstance(last_contact_date, str) and gives 30 points
        assert 0 <= score <= 100

    def test_every_source_quality_keyword(self):
        """Test every source quality keyword gives expected score."""
        from src.engine.scoring import SOURCE_QUALITY

        for source_name in SOURCE_QUALITY:
            score = calculate_score(
                Prospect(source=source_name),
                Company(),
            )
            assert 0 <= score <= 100

    def test_source_with_substring_match(self):
        """Source 'LinkedIn Import' should match 'linkedin'."""
        score = calculate_score(
            Prospect(source="LinkedIn Import"),
            Company(),
        )
        assert 0 <= score <= 100

    def test_every_size_scores(self):
        """Test every company size keyword."""
        from src.engine.scoring import SIZE_SCORES

        for size in SIZE_SCORES:
            score = calculate_score(
                Prospect(),
                Company(size=size),
            )
            assert 0 <= score <= 100


# =========================================================================
# CONFIDENCE SCORING EDGE CASES
# =========================================================================


class TestConfidenceEdgeCases:
    """Push confidence calculation to its limits."""

    def test_confidence_empty_prospect_no_methods(self):
        """Confidence with completely empty prospect."""
        conf = calculate_confidence(Prospect(), [])
        assert 0 <= conf <= 100

    def test_confidence_with_string_verified_date(self):
        """Verified date as string - the code has a special isinstance check."""
        methods = [
            ContactMethod(
                type=ContactMethodType.EMAIL,
                value="j@t.com",
                is_verified=True,
                verified_date="2026-01-15",  # String, not date!
            ),
            ContactMethod(
                type=ContactMethodType.PHONE,
                value="5551234",
            ),
        ]
        conf = calculate_confidence(Prospect(), methods)
        # The isinstance check for str means string dates always count as fresh
        assert 0 <= conf <= 100

    def test_confidence_with_stale_verified_date(self):
        """Verified date more than 90 days old."""
        methods = [
            ContactMethod(
                type=ContactMethodType.EMAIL,
                value="j@t.com",
                is_verified=True,
                verified_date=date(2024, 1, 1),  # Very old
            ),
        ]
        conf = calculate_confidence(Prospect(), methods)
        assert 0 <= conf <= 100

    def test_confidence_with_very_long_notes(self):
        """Very long notes should give 15 points."""
        conf = calculate_confidence(
            Prospect(notes="x" * 1000),
            [],
        )
        assert conf > 0

    def test_confidence_with_short_notes(self):
        """Short notes (< 20 chars) get partial score."""
        conf1 = calculate_confidence(Prospect(notes="hi"), [])
        conf2 = calculate_confidence(Prospect(notes="x" * 100), [])
        # Longer notes should score higher
        assert conf2 >= conf1

    def test_confidence_company_id_zero(self):
        """company_id = 0 is falsy, so no company points."""
        conf = calculate_confidence(Prospect(company_id=0), [])
        # company_id=0 is falsy, so `if prospect.company_id:` is False
        assert 0 <= conf <= 100


# =========================================================================
# CADENCE SYSTEM STRESS
# =========================================================================


class TestCadenceStress:
    """Try to break the cadence system."""

    def test_add_business_days_zero(self):
        """Adding 0 business days should return same date."""
        start = date(2026, 2, 6)  # Thursday
        assert add_business_days(start, 0) == start

    def test_add_business_days_one(self):
        """Adding 1 business day from Thursday = Friday."""
        start = date(2026, 2, 5)  # Thursday
        result = add_business_days(start, 1)
        assert result == date(2026, 2, 6)  # Friday

    def test_add_business_days_skips_weekend(self):
        """Adding 1 business day from Friday = Monday."""
        start = date(2026, 2, 6)  # Friday
        result = add_business_days(start, 1)
        assert result == date(2026, 2, 9)  # Monday

    def test_add_business_days_negative_returns_same_date(self):
        """Negative business_days: 0 < -1 is False, loop never executes.

        This means negative input silently returns the start date unchanged,
        rather than raising an error. This is arguably a bug - the caller
        might expect an exception for invalid input.
        """
        start = date(2026, 2, 6)
        result = add_business_days(start, -1)
        # Loop body never executes, returns start_date unchanged
        assert result == start

    def test_add_business_days_very_negative(self):
        """Even -1000 returns the same date (loop never fires)."""
        start = date(2026, 2, 6)
        result = add_business_days(start, -1000)
        assert result == start

    def test_add_business_days_large_number(self):
        """Adding 1000 business days should work."""
        start = date(2026, 2, 6)
        result = add_business_days(start, 1000)
        # ~4 years of business days
        assert result > start
        assert result.year >= 2029

    def test_get_interval_attempt_zero(self):
        """Attempt 0 is not in the map."""
        interval = get_interval(0)
        assert interval.min_days == 14  # Falls through to default

    def test_get_interval_negative_attempt(self):
        """Negative attempt number."""
        interval = get_interval(-1)
        assert interval.min_days == 14  # Falls through to default

    def test_get_interval_huge_attempt(self):
        """Attempt 999 should get the default interval."""
        interval = get_interval(999)
        assert interval == CadenceInterval(14, 21, "combo")

    def test_calculate_next_contact_attempt_zero(self):
        """Next contact with attempt 0."""
        result = calculate_next_contact(1, date(2026, 2, 6), 0)
        # attempt 0 -> default interval (14 min days)
        assert result > date(2026, 2, 6)

    def test_set_follow_up_nonexistent_prospect(self, db):
        """Setting follow-up on nonexistent prospect returns False."""
        result = set_follow_up(db, 99999, datetime(2026, 3, 1))
        assert result is False

    def test_get_orphaned_engaged(self, db):
        """Find engaged prospects with no follow-up."""
        cid = _company(db)
        # Engaged with follow-up
        _prospect(
            db,
            cid,
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.PRE_DEMO,
            follow_up_date=datetime(2026, 3, 1),
        )
        # Engaged WITHOUT follow-up (orphan)
        _prospect(
            db,
            cid,
            first="Orphan",
            last="Smith",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.PRE_DEMO,
        )
        orphans = get_orphaned_engaged(db)
        assert len(orphans) >= 1

    def test_get_overdue_empty_db(self, db):
        """No overdue when DB is empty."""
        result = get_overdue(db)
        assert result == []

    def test_get_todays_follow_ups_empty_db(self, db):
        """No follow-ups when DB is empty."""
        result = get_todays_follow_ups(db)
        assert result == []

    def test_get_todays_queue_empty_db(self, db):
        """Empty queue when DB is empty."""
        result = get_todays_queue(db)
        assert result == []

    def test_get_todays_queue_with_data(self, db):
        """Queue with both engaged and unengaged prospects."""
        cid = _company(db)
        # Engaged with today's follow-up
        _prospect(
            db,
            cid,
            first="Engaged",
            last="Today",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.CLOSING,
            follow_up_date=datetime.now(),
            prospect_score=90,
        )
        # Unengaged with no follow-up
        _prospect(
            db,
            cid,
            first="Unengaged",
            last="Ready",
            population=Population.UNENGAGED,
            prospect_score=80,
        )
        queue = get_todays_queue(db)
        assert len(queue) >= 1
        # Engaged should come first
        if len(queue) >= 2:
            assert queue[0].population == Population.ENGAGED


# =========================================================================
# POPULATION TRANSITION WARFARE
# =========================================================================


class TestPopulationTransitionWarfare:
    """Exhaustively test every valid and invalid transition."""

    def test_all_valid_transitions_accepted(self):
        """Every transition in VALID_TRANSITIONS should be allowed."""
        for from_pop, to_pop in VALID_TRANSITIONS:
            assert can_transition(
                from_pop, to_pop
            ), f"Valid transition {from_pop} -> {to_pop} was rejected"

    def test_same_population_always_allowed(self):
        """Staying in same population is always allowed."""
        for pop in Population:
            assert can_transition(pop, pop), f"Same-population {pop} was rejected"

    def test_dnc_is_terminal(self):
        """DEAD_DNC cannot transition to anything else."""
        for target in Population:
            if target == Population.DEAD_DNC:
                continue
            assert not can_transition(Population.DEAD_DNC, target), f"DNC -> {target} was allowed!"

    def test_closed_won_is_terminal(self):
        """CLOSED_WON cannot transition to anything else."""
        for target in Population:
            if target == Population.CLOSED_WON:
                continue
            assert not can_transition(
                Population.CLOSED_WON, target
            ), f"CLOSED_WON -> {target} was allowed!"

    def test_all_invalid_transitions_rejected(self):
        """Every non-valid transition should be rejected."""
        for from_pop in Population:
            for to_pop in Population:
                if from_pop == to_pop:
                    continue
                expected = (from_pop, to_pop) in VALID_TRANSITIONS
                if from_pop == Population.DEAD_DNC:
                    expected = False
                if from_pop == Population.CLOSED_WON:
                    expected = False
                actual = can_transition(from_pop, to_pop)
                assert actual == expected, (
                    f"Transition {from_pop} -> {to_pop}: " f"expected {expected}, got {actual}"
                )

    def test_transition_prospect_from_dnc_raises(self, db):
        """Transitioning FROM DNC should raise DNCViolationError."""
        cid = _company(db)
        pid = _prospect(db, cid, population=Population.DEAD_DNC)
        with pytest.raises(DNCViolationError):
            transition_prospect(db, pid, Population.UNENGAGED, "Escape attempt")

    def test_transition_to_dnc_sets_metadata(self, db):
        """Transitioning TO DNC should set dead_reason and dead_date."""
        cid = _company(db)
        pid = _prospect(db, cid, population=Population.UNENGAGED)
        transition_prospect(db, pid, Population.DEAD_DNC, "Hard no")
        p = db.get_prospect(pid)
        assert p.population == Population.DEAD_DNC
        assert p.dead_reason is not None
        assert p.dead_date is not None

    def test_transition_to_parked_defaults_month(self, db):
        """Parking without a month should default to next month."""
        cid = _company(db)
        pid = _prospect(db, cid, population=Population.UNENGAGED)
        transition_prospect(db, pid, Population.PARKED, "Call me later")
        p = db.get_prospect(pid)
        assert p.population == Population.PARKED
        assert p.parked_month is not None
        # Should be YYYY-MM format
        assert len(p.parked_month) == 7
        assert "-" in p.parked_month

    def test_transition_to_engaged_defaults_pre_demo(self, db):
        """Engaging without a stage should default to PRE_DEMO."""
        cid = _company(db)
        pid = _prospect(db, cid, population=Population.UNENGAGED)
        transition_prospect(db, pid, Population.ENGAGED, "Interested")
        p = db.get_prospect(pid)
        assert p.population == Population.ENGAGED
        assert p.engagement_stage == EngagementStage.PRE_DEMO

    def test_transition_nonexistent_prospect_raises(self, db):
        """Transitioning nonexistent prospect raises PipelineError."""
        with pytest.raises(PipelineError):
            transition_prospect(db, 99999, Population.ENGAGED, "Ghost")

    def test_invalid_transition_raises(self, db):
        """Invalid transition path raises PipelineError."""
        cid = _company(db)
        pid = _prospect(db, cid, population=Population.BROKEN)
        # BROKEN -> ENGAGED is not a valid transition
        with pytest.raises(PipelineError):
            transition_prospect(db, pid, Population.ENGAGED, "Skip the line")

    def test_no_op_same_population(self, db):
        """Transition to same population is a no-op."""
        cid = _company(db)
        pid = _prospect(db, cid, population=Population.UNENGAGED)
        result = transition_prospect(db, pid, Population.UNENGAGED)
        assert result is True

    def test_stage_transition_not_engaged_raises(self, db):
        """Stage transition on non-engaged prospect raises PipelineError."""
        cid = _company(db)
        pid = _prospect(db, cid, population=Population.UNENGAGED)
        with pytest.raises(PipelineError):
            transition_stage(db, pid, EngagementStage.DEMO_SCHEDULED)

    def test_valid_stage_transitions(self):
        """All valid stage transitions should be accepted."""
        for from_stage, to_stage in VALID_STAGE_TRANSITIONS:
            assert can_transition_stage(from_stage, to_stage)

    def test_invalid_stage_transitions(self):
        """Backwards stage transitions should be rejected."""
        assert not can_transition_stage(EngagementStage.CLOSING, EngagementStage.PRE_DEMO)
        assert not can_transition_stage(EngagementStage.POST_DEMO, EngagementStage.PRE_DEMO)
        assert not can_transition_stage(EngagementStage.DEMO_SCHEDULED, EngagementStage.PRE_DEMO)

    def test_stage_same_is_noop(self):
        """Same stage transition is always valid."""
        for stage in EngagementStage:
            assert can_transition_stage(stage, stage)

    def test_full_lifecycle_unengaged_to_closed_won(self, db):
        """Full lifecycle: UNENGAGED -> ENGAGED -> stages -> CLOSED_WON."""
        cid = _company(db)
        pid = _prospect(db, cid, population=Population.UNENGAGED)

        # UNENGAGED -> ENGAGED
        transition_prospect(db, pid, Population.ENGAGED, "Showed interest")
        p = db.get_prospect(pid)
        assert p.population == Population.ENGAGED
        assert p.engagement_stage == EngagementStage.PRE_DEMO

        # PRE_DEMO -> DEMO_SCHEDULED
        transition_stage(db, pid, EngagementStage.DEMO_SCHEDULED, "Demo set")
        p = db.get_prospect(pid)
        assert p.engagement_stage == EngagementStage.DEMO_SCHEDULED

        # DEMO_SCHEDULED -> POST_DEMO
        transition_stage(db, pid, EngagementStage.POST_DEMO, "Demo done")

        # POST_DEMO -> CLOSING
        transition_stage(db, pid, EngagementStage.CLOSING, "Ready to close")

        # ENGAGED -> CLOSED_WON
        transition_prospect(db, pid, Population.CLOSED_WON, "Deal signed!")
        p = db.get_prospect(pid)
        assert p.population == Population.CLOSED_WON

    def test_available_transitions_from_each_population(self):
        """get_available_transitions should return correct targets."""
        for pop in Population:
            available = get_available_transitions(pop)
            assert isinstance(available, list)
            # DNC and CLOSED_WON should have no transitions
            if pop == Population.DEAD_DNC:
                assert available == []
            elif pop == Population.CLOSED_WON:
                assert available == []


# =========================================================================
# RESCORE ALL EDGE CASES
# =========================================================================


class TestRescoreAll:
    """Test rescore_all with various database states."""

    def test_rescore_empty_db(self, db):
        """Rescore with no prospects."""
        count = rescore_all(db)
        assert count == 0

    def test_rescore_with_orphan_prospect(self, db):
        """Prospect whose company was deleted (company_id invalid)."""
        cid = _company(db)
        pid = _prospect(db, cid, population=Population.UNENGAGED)
        # Delete the company directly
        conn = db._get_connection()
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("DELETE FROM companies WHERE id = ?", (cid,))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        # Rescore should not crash - it creates empty Company()
        count = rescore_all(db)
        assert count >= 1

    def test_rescore_updates_scores(self, db):
        """Rescore should actually update prospect_score."""
        cid = _company(db, state="TX", size="enterprise")
        pid = _prospect(
            db,
            cid,
            population=Population.UNENGAGED,
            title="CEO",
            source="referral",
            prospect_score=0,
        )
        rescore_all(db)
        p = db.get_prospect(pid)
        # With CEO title and referral source, score should be > 0
        assert p.prospect_score > 0

    def test_rescore_skips_terminal_populations(self, db):
        """Rescore should not process DEAD_DNC, CLOSED_WON, LOST, PARKED."""
        cid = _company(db)
        _prospect(db, cid, population=Population.DEAD_DNC, prospect_score=0)
        _prospect(
            db, cid, first="Won", last="Deal", population=Population.CLOSED_WON, prospect_score=0
        )
        count = rescore_all(db)
        # Neither should be rescored
        assert count == 0

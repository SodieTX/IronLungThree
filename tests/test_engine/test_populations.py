"""Tests for population transitions.

Tests Step 2.1: Population Manager
    - Valid transitions with activity logging
    - Invalid transition rejection
    - DNC terminal enforcement
    - Engagement stage transitions
    - Full lifecycle walk-through
"""

from datetime import date, timedelta

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
from src.engine.populations import (
    VALID_TRANSITIONS,
    can_transition,
    can_transition_stage,
    get_available_transitions,
    transition_prospect,
    transition_stage,
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
def company_id(db):
    """Create a test company, return its ID."""
    company = Company(name="Test Corp", state="TX")
    return db.create_company(company)


@pytest.fixture
def unengaged_prospect_id(db, company_id):
    """Create an unengaged prospect, return its ID."""
    prospect = Prospect(
        company_id=company_id,
        first_name="John",
        last_name="Smith",
        population=Population.UNENGAGED,
        prospect_score=75,
    )
    pid = db.create_prospect(prospect)
    # Add contact methods so it's "complete"
    db.create_contact_method(
        ContactMethod(prospect_id=pid, type=ContactMethodType.EMAIL, value="john@test.com")
    )
    db.create_contact_method(
        ContactMethod(prospect_id=pid, type=ContactMethodType.PHONE, value="5551234567")
    )
    return pid


@pytest.fixture
def engaged_prospect_id(db, company_id):
    """Create an engaged prospect, return its ID."""
    prospect = Prospect(
        company_id=company_id,
        first_name="Jane",
        last_name="Doe",
        population=Population.ENGAGED,
        engagement_stage=EngagementStage.PRE_DEMO,
        prospect_score=90,
    )
    return db.create_prospect(prospect)


@pytest.fixture
def dnc_prospect_id(db, company_id):
    """Create a DNC prospect, return its ID."""
    prospect = Prospect(
        company_id=company_id,
        first_name="Bad",
        last_name="Contact",
        population=Population.DEAD_DNC,
    )
    return db.create_prospect(prospect)


@pytest.fixture
def broken_prospect_id(db, company_id):
    """Create a broken prospect, return its ID."""
    prospect = Prospect(
        company_id=company_id,
        first_name="Broken",
        last_name="Record",
        population=Population.BROKEN,
    )
    return db.create_prospect(prospect)


# =============================================================================
# TRANSITION VALIDATION (can_transition)
# =============================================================================


class TestValidTransitions:
    """Test transition validation rules."""

    def test_unengaged_can_go_to_engaged(self):
        """Unengaged -> Engaged is valid."""
        assert can_transition(Population.UNENGAGED, Population.ENGAGED)

    def test_unengaged_can_go_to_dead_dnc(self):
        """Unengaged -> Dead/DNC is valid."""
        assert can_transition(Population.UNENGAGED, Population.DEAD_DNC)

    def test_unengaged_can_go_to_parked(self):
        """Unengaged -> Parked is valid."""
        assert can_transition(Population.UNENGAGED, Population.PARKED)

    def test_unengaged_can_go_to_lost(self):
        """Unengaged -> Lost is valid."""
        assert can_transition(Population.UNENGAGED, Population.LOST)

    def test_unengaged_can_go_to_broken(self):
        """Unengaged -> Broken is valid (data degraded)."""
        assert can_transition(Population.UNENGAGED, Population.BROKEN)

    def test_dead_dnc_cannot_transition_anywhere(self):
        """Dead/DNC cannot transition to any population."""
        for pop in Population:
            if pop != Population.DEAD_DNC:
                assert not can_transition(Population.DEAD_DNC, pop)

    def test_closed_won_cannot_transition_anywhere(self):
        """Closed Won cannot transition to any population."""
        for pop in Population:
            if pop != Population.CLOSED_WON:
                assert not can_transition(Population.CLOSED_WON, pop)

    def test_engaged_can_go_to_closed_won(self):
        """Engaged -> Closed Won is valid."""
        assert can_transition(Population.ENGAGED, Population.CLOSED_WON)

    def test_engaged_can_go_to_lost(self):
        """Engaged -> Lost is valid."""
        assert can_transition(Population.ENGAGED, Population.LOST)

    def test_engaged_can_go_to_parked(self):
        """Engaged -> Parked is valid."""
        assert can_transition(Population.ENGAGED, Population.PARKED)

    def test_broken_can_go_to_unengaged(self):
        """Broken -> Unengaged is valid (data found)."""
        assert can_transition(Population.BROKEN, Population.UNENGAGED)

    def test_parked_can_go_to_unengaged(self):
        """Parked -> Unengaged is valid (month arrived)."""
        assert can_transition(Population.PARKED, Population.UNENGAGED)

    def test_lost_can_go_to_unengaged(self):
        """Lost -> Unengaged is valid (resurrection)."""
        assert can_transition(Population.LOST, Population.UNENGAGED)

    def test_partnership_can_go_to_unengaged(self):
        """Partnership -> Unengaged is valid (promotion)."""
        assert can_transition(Population.PARTNERSHIP, Population.UNENGAGED)

    def test_partnership_can_go_to_engaged(self):
        """Partnership -> Engaged is valid (promotion)."""
        assert can_transition(Population.PARTNERSHIP, Population.ENGAGED)

    def test_same_population_always_valid(self):
        """Transitioning to same population is always valid."""
        for pop in Population:
            assert can_transition(pop, pop)

    def test_invalid_broken_to_engaged(self):
        """Broken -> Engaged is invalid (must go through unengaged)."""
        assert not can_transition(Population.BROKEN, Population.ENGAGED)

    def test_invalid_lost_to_engaged(self):
        """Lost -> Engaged is invalid (must resurrect to unengaged first)."""
        assert not can_transition(Population.LOST, Population.ENGAGED)


# =============================================================================
# ENGAGEMENT STAGES (can_transition_stage)
# =============================================================================


class TestEngagementStages:
    """Test engagement stage transitions."""

    def test_pre_demo_to_demo_scheduled(self):
        """Pre-Demo -> Demo Scheduled is valid."""
        assert can_transition_stage(EngagementStage.PRE_DEMO, EngagementStage.DEMO_SCHEDULED)

    def test_demo_scheduled_to_post_demo(self):
        """Demo Scheduled -> Post Demo is valid."""
        assert can_transition_stage(EngagementStage.DEMO_SCHEDULED, EngagementStage.POST_DEMO)

    def test_post_demo_to_closing(self):
        """Post Demo -> Closing is valid."""
        assert can_transition_stage(EngagementStage.POST_DEMO, EngagementStage.CLOSING)

    def test_cannot_skip_stages(self):
        """Cannot skip from Pre-Demo to Closing."""
        assert not can_transition_stage(EngagementStage.PRE_DEMO, EngagementStage.CLOSING)

    def test_cannot_go_backwards(self):
        """Cannot go from Closing back to Pre-Demo."""
        assert not can_transition_stage(EngagementStage.CLOSING, EngagementStage.PRE_DEMO)

    def test_same_stage_is_valid(self):
        """Same stage transition is valid (no-op)."""
        assert can_transition_stage(EngagementStage.PRE_DEMO, EngagementStage.PRE_DEMO)


# =============================================================================
# TRANSITION EXECUTION (transition_prospect)
# =============================================================================


class TestTransitionProspect:
    """Test prospect transition function."""

    def test_transition_updates_prospect(self, db, unengaged_prospect_id):
        """Transition updates prospect population."""
        fu = date.today() + timedelta(days=3)
        result = transition_prospect(
            db, unengaged_prospect_id, Population.ENGAGED,
            reason="Showed interest", follow_up_date=fu,
        )
        assert result is True

        prospect = db.get_prospect(unengaged_prospect_id)
        assert prospect.population == Population.ENGAGED

    def test_transition_logs_activity(self, db, unengaged_prospect_id):
        """Transition creates an activity record."""
        fu = date.today() + timedelta(days=3)
        transition_prospect(
            db, unengaged_prospect_id, Population.ENGAGED,
            reason="Showed interest", follow_up_date=fu,
        )

        activities = db.get_activities(unengaged_prospect_id)
        assert len(activities) >= 1
        activity = activities[0]
        assert activity.activity_type == ActivityType.STATUS_CHANGE
        assert activity.population_before == Population.UNENGAGED
        assert activity.population_after == Population.ENGAGED
        assert "Showed interest" in activity.notes

    def test_transition_to_engaged_sets_pre_demo(self, db, unengaged_prospect_id):
        """Transitioning to ENGAGED defaults to PRE_DEMO stage."""
        fu = date.today() + timedelta(days=3)
        transition_prospect(db, unengaged_prospect_id, Population.ENGAGED, follow_up_date=fu)

        prospect = db.get_prospect(unengaged_prospect_id)
        assert prospect.engagement_stage == EngagementStage.PRE_DEMO

    def test_transition_to_engaged_with_stage(self, db, unengaged_prospect_id):
        """Transitioning to ENGAGED with explicit stage."""
        fu = date.today() + timedelta(days=3)
        transition_prospect(
            db,
            unengaged_prospect_id,
            Population.ENGAGED,
            to_stage=EngagementStage.DEMO_SCHEDULED,
            follow_up_date=fu,
        )

        prospect = db.get_prospect(unengaged_prospect_id)
        assert prospect.engagement_stage == EngagementStage.DEMO_SCHEDULED

    def test_transition_to_engaged_without_follow_up_raises(self, db, unengaged_prospect_id):
        """Transitioning to ENGAGED without follow-up date raises PipelineError."""
        with pytest.raises(PipelineError, match="follow-up date"):
            transition_prospect(
                db, unengaged_prospect_id, Population.ENGAGED, reason="Showed interest"
            )

    def test_transition_to_engaged_with_existing_follow_up(self, db, company_id):
        """Prospect with existing follow_up_date can transition to ENGAGED."""
        fu = date.today() + timedelta(days=5)
        prospect = Prospect(
            company_id=company_id,
            first_name="Has",
            last_name="FollowUp",
            population=Population.UNENGAGED,
            follow_up_date=fu,
        )
        pid = db.create_prospect(prospect)
        result = transition_prospect(db, pid, Population.ENGAGED, reason="Had date already")
        assert result is True

    def test_transition_to_engaged_sets_follow_up_date(self, db, unengaged_prospect_id):
        """Follow-up date passed to transition is set on the prospect."""
        fu = date.today() + timedelta(days=7)
        transition_prospect(
            db, unengaged_prospect_id, Population.ENGAGED,
            reason="Interest", follow_up_date=fu,
        )
        prospect = db.get_prospect(unengaged_prospect_id)
        assert prospect.follow_up_date is not None

    def test_transition_away_from_engaged_clears_stage(self, db, engaged_prospect_id):
        """Leaving ENGAGED clears engagement stage."""
        transition_prospect(db, engaged_prospect_id, Population.PARKED)

        prospect = db.get_prospect(engaged_prospect_id)
        assert prospect.population == Population.PARKED
        assert prospect.engagement_stage is None

    def test_dnc_transition_raises_error(self, db, dnc_prospect_id):
        """Transitioning FROM DNC raises DNCViolationError."""
        with pytest.raises(DNCViolationError):
            transition_prospect(db, dnc_prospect_id, Population.UNENGAGED)

    def test_invalid_transition_raises_error(self, db, broken_prospect_id):
        """Invalid transition raises PipelineError."""
        with pytest.raises(PipelineError):
            transition_prospect(db, broken_prospect_id, Population.ENGAGED)

    def test_nonexistent_prospect_raises_error(self, db):
        """Non-existent prospect raises PipelineError."""
        with pytest.raises(PipelineError):
            transition_prospect(db, 9999, Population.ENGAGED)

    def test_transition_to_dnc_sets_dead_fields(self, db, unengaged_prospect_id):
        """Transitioning to DNC sets dead_reason and dead_date."""
        transition_prospect(db, unengaged_prospect_id, Population.DEAD_DNC, reason="Requested DNC")

        prospect = db.get_prospect(unengaged_prospect_id)
        assert prospect.population == Population.DEAD_DNC
        assert prospect.dead_reason is not None
        assert prospect.dead_date is not None

    def test_same_population_noop(self, db, unengaged_prospect_id):
        """Same population transition is a no-op."""
        result = transition_prospect(db, unengaged_prospect_id, Population.UNENGAGED)
        assert result is True


# =============================================================================
# STAGE TRANSITION EXECUTION (transition_stage)
# =============================================================================


class TestTransitionStage:
    """Test engagement stage transition function."""

    def test_stage_transition_updates(self, db, engaged_prospect_id):
        """Stage transition updates the prospect."""
        result = transition_stage(db, engaged_prospect_id, EngagementStage.DEMO_SCHEDULED)
        assert result is True

        prospect = db.get_prospect(engaged_prospect_id)
        assert prospect.engagement_stage == EngagementStage.DEMO_SCHEDULED

    def test_stage_transition_logs_activity(self, db, engaged_prospect_id):
        """Stage transition creates activity with stage_before/stage_after."""
        transition_stage(
            db,
            engaged_prospect_id,
            EngagementStage.DEMO_SCHEDULED,
            reason="Demo booked for Wednesday",
        )

        activities = db.get_activities(engaged_prospect_id)
        assert len(activities) >= 1
        activity = activities[0]
        assert activity.stage_before == EngagementStage.PRE_DEMO
        assert activity.stage_after == EngagementStage.DEMO_SCHEDULED

    def test_non_engaged_raises_error(self, db, unengaged_prospect_id):
        """Stage transition on non-engaged raises PipelineError."""
        with pytest.raises(PipelineError):
            transition_stage(db, unengaged_prospect_id, EngagementStage.DEMO_SCHEDULED)

    def test_invalid_stage_skip_raises_error(self, db, engaged_prospect_id):
        """Skipping stages raises PipelineError."""
        with pytest.raises(PipelineError):
            transition_stage(db, engaged_prospect_id, EngagementStage.CLOSING)


# =============================================================================
# AVAILABLE TRANSITIONS
# =============================================================================


class TestAvailableTransitions:
    """Test get_available_transitions helper."""

    def test_unengaged_options(self):
        """Unengaged has multiple transition options."""
        options = get_available_transitions(Population.UNENGAGED)
        assert Population.ENGAGED in options
        assert Population.PARKED in options
        assert Population.DEAD_DNC in options

    def test_dnc_has_no_options(self):
        """DNC has no available transitions."""
        options = get_available_transitions(Population.DEAD_DNC)
        assert len(options) == 0

    def test_closed_won_has_no_options(self):
        """Closed Won has no available transitions."""
        options = get_available_transitions(Population.CLOSED_WON)
        assert len(options) == 0


# =============================================================================
# FULL LIFECYCLE
# =============================================================================


class TestFullLifecycle:
    """Test walking a prospect through the full pipeline lifecycle."""

    def test_full_lifecycle_unengaged_to_closed_won(self, db, company_id):
        """Walk prospect: broken -> unengaged -> engaged (all stages) -> closed won."""
        # Start as broken
        prospect = Prospect(
            company_id=company_id,
            first_name="Lifecycle",
            last_name="Test",
            population=Population.BROKEN,
        )
        pid = db.create_prospect(prospect)

        # broken -> unengaged (data found)
        transition_prospect(db, pid, Population.UNENGAGED, reason="Email found")
        p = db.get_prospect(pid)
        assert p.population == Population.UNENGAGED

        # unengaged -> engaged (showed interest)
        fu = date.today() + timedelta(days=5)
        transition_prospect(db, pid, Population.ENGAGED, reason="Replied to email", follow_up_date=fu)
        p = db.get_prospect(pid)
        assert p.population == Population.ENGAGED
        assert p.engagement_stage == EngagementStage.PRE_DEMO

        # pre_demo -> demo_scheduled
        transition_stage(db, pid, EngagementStage.DEMO_SCHEDULED)
        p = db.get_prospect(pid)
        assert p.engagement_stage == EngagementStage.DEMO_SCHEDULED

        # demo_scheduled -> post_demo
        transition_stage(db, pid, EngagementStage.POST_DEMO)
        p = db.get_prospect(pid)
        assert p.engagement_stage == EngagementStage.POST_DEMO

        # post_demo -> closing
        transition_stage(db, pid, EngagementStage.CLOSING)
        p = db.get_prospect(pid)
        assert p.engagement_stage == EngagementStage.CLOSING

        # engaged -> closed_won
        transition_prospect(db, pid, Population.CLOSED_WON, reason="Deal signed!")
        p = db.get_prospect(pid)
        assert p.population == Population.CLOSED_WON

        # Verify all transitions were logged
        activities = db.get_activities(pid)
        status_changes = [a for a in activities if a.activity_type == ActivityType.STATUS_CHANGE]
        # 2 population transitions + 3 stage transitions + closing = 6
        assert len(status_changes) >= 5

    def test_lifecycle_park_and_return(self, db, unengaged_prospect_id):
        """Park a prospect and bring them back."""
        # unengaged -> parked
        transition_prospect(db, unengaged_prospect_id, Population.PARKED, reason="Call me in June")
        p = db.get_prospect(unengaged_prospect_id)
        assert p.population == Population.PARKED

        # parked -> unengaged (month arrived)
        transition_prospect(db, unengaged_prospect_id, Population.UNENGAGED, reason="June arrived")
        p = db.get_prospect(unengaged_prospect_id)
        assert p.population == Population.UNENGAGED

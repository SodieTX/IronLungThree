"""Population management and transition rules.

The most important logic in the system: who can move where.

Valid transitions are explicitly defined. DNC is terminal - no way out.

Usage:
    from src.engine.populations import can_transition, transition_prospect

    if can_transition(Population.UNENGAGED, Population.ENGAGED):
        transition_prospect(prospect_id, Population.ENGAGED, "Showed interest")
"""

from datetime import datetime
from typing import Optional, Set, Tuple

from src.core.exceptions import DNCViolationError, PipelineError
from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import EngagementStage, Population

logger = get_logger(__name__)


# =============================================================================
# VALID TRANSITIONS
# =============================================================================

# Population transitions (where in the pipeline)
VALID_TRANSITIONS: Set[Tuple[Population, Population]] = {
    # From BROKEN
    (Population.BROKEN, Population.UNENGAGED),  # Data found
    (Population.BROKEN, Population.DEAD_DNC),  # DNC from broken
    # From UNENGAGED
    (Population.UNENGAGED, Population.BROKEN),  # Data degraded
    (Population.UNENGAGED, Population.ENGAGED),  # Showed interest
    (Population.UNENGAGED, Population.PARKED),  # "Call me in June"
    (Population.UNENGAGED, Population.DEAD_DNC),  # Hard no
    (Population.UNENGAGED, Population.LOST),  # Lost before engagement
    # From ENGAGED
    (Population.ENGAGED, Population.PARKED),  # "Not right now"
    (Population.ENGAGED, Population.DEAD_DNC),  # Hard no
    (Population.ENGAGED, Population.LOST),  # Lost deal
    (Population.ENGAGED, Population.CLOSED_WON),  # Won from any stage!
    # From PARKED
    (Population.PARKED, Population.UNENGAGED),  # Month arrived
    (Population.PARKED, Population.DEAD_DNC),  # Hard no
    # From LOST
    (Population.LOST, Population.UNENGAGED),  # Resurrection (12+ months)
    # From PARTNERSHIP
    (Population.PARTNERSHIP, Population.UNENGAGED),  # Promotion
    (Population.PARTNERSHIP, Population.ENGAGED),  # Promotion
}

# Engagement stage transitions (within ENGAGED)
VALID_STAGE_TRANSITIONS: Set[Tuple[EngagementStage, EngagementStage]] = {
    (EngagementStage.PRE_DEMO, EngagementStage.DEMO_SCHEDULED),
    (EngagementStage.DEMO_SCHEDULED, EngagementStage.POST_DEMO),
    (EngagementStage.POST_DEMO, EngagementStage.CLOSING),
}


def can_transition(from_pop: Population, to_pop: Population) -> bool:
    """Check if a population transition is valid.

    Args:
        from_pop: Current population
        to_pop: Target population

    Returns:
        True if transition is allowed
    """
    # No change = always allowed
    if from_pop == to_pop:
        return True

    # DNC is terminal - no way out
    if from_pop == Population.DEAD_DNC:
        return False

    # CLOSED_WON is terminal - celebrate, don't regress
    if from_pop == Population.CLOSED_WON:
        return False

    return (from_pop, to_pop) in VALID_TRANSITIONS


def can_transition_stage(from_stage: EngagementStage, to_stage: EngagementStage) -> bool:
    """Check if an engagement stage transition is valid.

    Args:
        from_stage: Current stage
        to_stage: Target stage

    Returns:
        True if transition is allowed
    """
    if from_stage == to_stage:
        return True
    return (from_stage, to_stage) in VALID_STAGE_TRANSITIONS


def transition_prospect(
    db: Database,
    prospect_id: int,
    to_population: Population,
    reason: Optional[str] = None,
    to_stage: Optional[EngagementStage] = None,
) -> bool:
    """Execute a population transition with full logging.

    Args:
        db: Database instance
        prospect_id: Prospect to transition
        to_population: Target population
        reason: Reason for transition
        to_stage: Target engagement stage (if moving to ENGAGED)

    Returns:
        True if transition successful

    Raises:
        DNCViolationError: If trying to transition FROM DNC
        PipelineError: If transition is invalid
    """
    from src.db.models import Activity, ActivityType

    prospect = db.get_prospect(prospect_id)
    if prospect is None:
        raise PipelineError(f"Prospect {prospect_id} not found")

    from_pop = prospect.population

    # DNC is terminal - absolute, no exceptions
    if from_pop == Population.DEAD_DNC:
        raise DNCViolationError(
            f"Cannot transition prospect {prospect_id} from DNC - DNC is permanent"
        )

    # No-op if already there
    if from_pop == to_population and to_stage is None:
        return True

    # Validate transition
    if not can_transition(from_pop, to_population):
        raise PipelineError(f"Invalid transition: {from_pop.value} -> {to_population.value}")

    # Build update fields
    old_stage = prospect.engagement_stage
    new_stage = to_stage

    # If moving to ENGAGED and no stage specified, default to PRE_DEMO
    if to_population == Population.ENGAGED and new_stage is None:
        new_stage = EngagementStage.PRE_DEMO

    # If leaving ENGAGED, clear engagement stage
    if to_population != Population.ENGAGED:
        new_stage = None

    # Update the prospect
    prospect.population = to_population
    prospect.engagement_stage = new_stage

    # Set metadata for terminal states
    if to_population == Population.DEAD_DNC:
        from datetime import date as date_type
        from datetime import datetime as datetime_type

        from src.db.models import DeadReason

        prospect.dead_reason = DeadReason.DNC
        prospect.dead_date = date_type.today()
        # Store precise timestamp for grace period reversal
        _set_dnc_timestamp(db, prospect_id, datetime_type.now())

    if to_population == Population.PARKED and prospect.parked_month is None:
        # Default to next month if not set
        from datetime import date as date_type

        today = date_type.today()
        month = today.month + 1
        year = today.year
        if month > 12:
            month = 1
            year += 1
        prospect.parked_month = f"{year}-{month:02d}"

    db.update_prospect(prospect)

    # When moving to BROKEN, ensure a research_queue entry exists so the Broken tab
    # can display the record (In Progress section). Intake creates these for new
    # imports, but prospects sequestered via transition or Trello sync do not.
    if to_population == Population.BROKEN:
        from src.db.models import ResearchTask

        conn = db._get_connection()
        existing = conn.execute(
            "SELECT 1 FROM research_queue WHERE prospect_id = ? LIMIT 1",
            (prospect_id,),
        ).fetchone()
        if not existing:
            db.create_research_task(
                ResearchTask(prospect_id=prospect_id, priority=0),
            )
            logger.info(
                "Created research task for sequestered broken prospect",
                extra={"context": {"prospect_id": prospect_id}},
            )

    # Log the transition activity
    activity = Activity(
        prospect_id=prospect_id,
        activity_type=ActivityType.STATUS_CHANGE,
        population_before=from_pop,
        population_after=to_population,
        stage_before=old_stage,
        stage_after=new_stage,
        notes=reason or f"Transition: {from_pop.value} -> {to_population.value}",
        created_by="user",
    )
    db.create_activity(activity)

    logger.info(
        "Prospect transitioned",
        extra={
            "context": {
                "prospect_id": prospect_id,
                "from": from_pop.value,
                "to": to_population.value,
                "reason": reason,
            }
        },
    )

    return True


def transition_stage(
    db: Database,
    prospect_id: int,
    to_stage: EngagementStage,
    reason: Optional[str] = None,
) -> bool:
    """Change engagement stage within ENGAGED population.

    Args:
        db: Database instance
        prospect_id: Prospect to transition
        to_stage: Target stage
        reason: Reason for transition

    Returns:
        True if transition successful

    Raises:
        PipelineError: If prospect not engaged or invalid transition
    """
    from src.db.models import Activity, ActivityType

    prospect = db.get_prospect(prospect_id)
    if prospect is None:
        raise PipelineError(f"Prospect {prospect_id} not found")

    if prospect.population != Population.ENGAGED:
        raise PipelineError(
            f"Prospect {prospect_id} is not engaged (population={prospect.population.value})"
        )

    old_stage = prospect.engagement_stage
    if old_stage is None:
        old_stage = EngagementStage.PRE_DEMO

    # No-op if already at target stage
    if old_stage == to_stage:
        return True

    if not can_transition_stage(old_stage, to_stage):
        raise PipelineError(f"Invalid stage transition: {old_stage.value} -> {to_stage.value}")

    # Update the prospect
    prospect.engagement_stage = to_stage
    db.update_prospect(prospect)

    # Log the stage transition
    activity = Activity(
        prospect_id=prospect_id,
        activity_type=ActivityType.STATUS_CHANGE,
        population_before=Population.ENGAGED,
        population_after=Population.ENGAGED,
        stage_before=old_stage,
        stage_after=to_stage,
        notes=reason or f"Stage: {old_stage.value} -> {to_stage.value}",
        created_by="user",
    )
    db.create_activity(activity)

    logger.info(
        "Engagement stage changed",
        extra={
            "context": {
                "prospect_id": prospect_id,
                "from_stage": old_stage.value,
                "to_stage": to_stage.value,
            }
        },
    )

    return True


def get_available_transitions(population: Population) -> list[Population]:
    """Get list of valid target populations.

    Args:
        population: Current population

    Returns:
        List of populations this can transition to
    """
    return [to_pop for (from_pop, to_pop) in VALID_TRANSITIONS if from_pop == population]


# =============================================================================
# DNC GRACE PERIOD (24-hour reversal window)
# =============================================================================

_DNC_GRACE_HOURS = 24


def _set_dnc_timestamp(db: Database, prospect_id: int, timestamp: datetime) -> None:
    """Store the exact moment a prospect was moved to DNC.

    Uses system_metadata with a prospect-specific key.
    """
    key = f"dnc_timestamp_{prospect_id}"
    db.upsert_system_metadata(key, timestamp.isoformat())


def _get_dnc_timestamp(db: Database, prospect_id: int) -> Optional[datetime]:
    """Retrieve the DNC timestamp for a prospect."""
    key = f"dnc_timestamp_{prospect_id}"
    value = db.get_system_metadata(key)
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _clear_dnc_timestamp(db: Database, prospect_id: int) -> None:
    """Remove the DNC timestamp after grace period use or expiry."""
    key = f"dnc_timestamp_{prospect_id}"
    conn = db._get_connection()
    conn.execute("DELETE FROM system_metadata WHERE key = ?", (key,))
    conn.commit()


def can_reverse_dnc(db: Database, prospect_id: int) -> bool:
    """Check if a DNC decision can still be reversed (within grace period).

    Args:
        db: Database instance
        prospect_id: Prospect to check

    Returns:
        True if within the 24-hour grace window
    """
    from datetime import timedelta

    ts = _get_dnc_timestamp(db, prospect_id)
    if ts is None:
        return False
    elapsed = datetime.now() - ts
    return bool(elapsed < timedelta(hours=_DNC_GRACE_HOURS))


def reverse_dnc(
    db: Database,
    prospect_id: int,
    restore_to: Population = Population.UNENGAGED,
    reason: Optional[str] = None,
) -> bool:
    """Reverse a DNC decision within the grace period.

    This is the ONLY way out of DNC, and only within 24 hours.

    Args:
        db: Database instance
        prospect_id: Prospect to reverse
        restore_to: Population to restore to (default UNENGAGED)
        reason: Why the reversal happened

    Returns:
        True if reversed successfully

    Raises:
        PipelineError: If grace period has expired
    """
    from src.db.models import Activity, ActivityType

    if not can_reverse_dnc(db, prospect_id):
        raise PipelineError(
            f"Cannot reverse DNC for prospect {prospect_id}: "
            "grace period expired or no timestamp found"
        )

    prospect = db.get_prospect(prospect_id)
    if prospect is None:
        raise PipelineError(f"Prospect {prospect_id} not found")

    if prospect.population != Population.DEAD_DNC:
        raise PipelineError(
            f"Prospect {prospect_id} is not DNC (current: {prospect.population.value})"
        )

    # Perform the reversal — bypass normal transition rules
    prospect.population = restore_to
    prospect.dead_reason = None
    prospect.dead_date = None
    prospect.engagement_stage = None

    db.update_prospect(prospect)
    _clear_dnc_timestamp(db, prospect_id)

    # Log the reversal
    activity = Activity(
        prospect_id=prospect_id,
        activity_type=ActivityType.STATUS_CHANGE,
        notes=(
            f"DNC REVERSED within grace period -> {restore_to.value}. "
            f"Reason: {reason or 'No reason given'}"
        ),
        created_by="user",
    )
    db.create_activity(activity)

    logger.info(
        f"DNC reversed for prospect {prospect_id}",
        extra={
            "context": {
                "prospect_id": prospect_id,
                "restored_to": restore_to.value,
                "reason": reason,
            }
        },
    )
    return True

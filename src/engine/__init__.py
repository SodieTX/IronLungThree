"""Engine package - Business logic layer.

This package contains all business logic:
    - Population management and transitions
    - Cadence calculations
    - Scoring algorithms
    - Research automation
    - Nurture sequences
    - Learning engine

Modules:
    - populations: Population transitions and rules
    - cadence: Dual cadence system
    - scoring: Prospect scoring algorithm
    - research: Autonomous research
    - groundskeeper: Data maintenance
    - nurture: Email nurture sequences
    - learning: Note-based learning
    - intervention: Decay detection
    - templates: Email templates
    - email_gen: AI email generation
    - demo_prep: Demo preparation
    - export: Data export
"""

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
from src.engine.populations import (
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
)

__all__ = [
    # Populations (Phase 2, Step 2.1)
    "VALID_TRANSITIONS",
    "can_transition",
    "can_transition_stage",
    "get_available_transitions",
    "transition_prospect",
    "transition_stage",
    # Scoring (Phase 2, Step 2.2)
    "DEFAULT_WEIGHTS",
    "ScoreWeights",
    "calculate_confidence",
    "calculate_score",
    # Cadence (Phase 2, Steps 2.3-2.4)
    "DEFAULT_INTERVALS",
    "add_business_days",
    "calculate_next_contact",
    "get_interval",
    "get_orphaned_engaged",
    "get_overdue",
    "get_todays_follow_ups",
    "get_todays_queue",
    "set_follow_up",
]

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

from src.engine.populations import (
    VALID_TRANSITIONS,
    can_transition,
)

__all__ = [
    "VALID_TRANSITIONS",
    "can_transition",
]

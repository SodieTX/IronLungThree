"""Database package - SQLite database, models, backup, intake.

This package provides all database functionality:
    - database: Connection management and CRUD operations
    - models: Dataclasses and enumerations
    - backup: Backup and restore functionality
    - intake: Import deduplication and DNC protection

Modules:
    - database: SQLite connection and operations
    - models: Data models and enumerations
    - backup: Backup system
    - intake: Import funnel with dedup and DNC protection
"""

from src.db.models import (
    Population,
    EngagementStage,
    ActivityType,
    ActivityOutcome,
    LostReason,
    ContactMethodType,
    AttemptType,
    ResearchStatus,
    IntelCategory,
    Company,
    Prospect,
    ContactMethod,
    Activity,
    ImportSource,
    ResearchTask,
    IntelNugget,
    ProspectTag,
)

__all__ = [
    # Enums
    "Population",
    "EngagementStage",
    "ActivityType",
    "ActivityOutcome",
    "LostReason",
    "ContactMethodType",
    "AttemptType",
    "ResearchStatus",
    "IntelCategory",
    # Dataclasses
    "Company",
    "Prospect",
    "ContactMethod",
    "Activity",
    "ImportSource",
    "ResearchTask",
    "IntelNugget",
    "ProspectTag",
]

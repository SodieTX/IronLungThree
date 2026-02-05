"""Card story generator - Narrative context per prospect.

Generates narrative from notes:
    "You first called John in November. He was interested but said
    Q1 was too early. You parked him for March. March is here."
"""

from src.db.database import Database
from src.core.logging import get_logger

logger = get_logger(__name__)


def generate_story(db: Database, prospect_id: int) -> str:
    """Generate narrative from prospect history."""
    raise NotImplementedError("Phase 4, Step 4.8")


def _summarize_timeline(activities: list) -> str:
    """Create timeline summary."""
    raise NotImplementedError("Phase 4, Step 4.8")


def _extract_key_moments(activities: list) -> list[str]:
    """Find key moments in history."""
    raise NotImplementedError("Phase 4, Step 4.8")

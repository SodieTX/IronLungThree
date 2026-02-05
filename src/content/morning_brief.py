"""Morning brief generation."""

from dataclasses import dataclass

from src.core.logging import get_logger
from src.db.database import Database

logger = get_logger(__name__)


@dataclass
class MorningBrief:
    """Morning brief content."""

    date: str
    pipeline_summary: str
    todays_work: str
    overnight_changes: str
    warnings: list[str]
    full_text: str


def generate_morning_brief(db: Database) -> MorningBrief:
    """Generate morning brief content."""
    raise NotImplementedError("Phase 2, Step 2.7")

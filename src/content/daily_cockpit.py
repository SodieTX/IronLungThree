"""Daily cockpit data generation."""

from dataclasses import dataclass
from src.db.database import Database
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CockpitData:
    """Real-time cockpit metrics."""

    queue_remaining: int
    queue_total: int
    engaged_count: int
    demos_today: int
    overdue_count: int


def get_cockpit_data(db: Database) -> CockpitData:
    """Get current cockpit data."""
    raise NotImplementedError("Phase 2")

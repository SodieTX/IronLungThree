"""Glanceable dashboard - One-second progress read."""

from dataclasses import dataclass
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DashboardData:
    cards_processed: int
    cards_total: int
    calls_made: int
    emails_sent: int
    demos_scheduled: int
    current_streak: int


def get_dashboard_data() -> DashboardData:
    """Get current dashboard stats."""
    raise NotImplementedError("Phase 6, Step 6.6")


def refresh_dashboard() -> None:
    """Refresh dashboard display."""
    raise NotImplementedError("Phase 6, Step 6.6")

"""Rescue engine for zero-capacity mode.

When Jeff is having a bad day:
    - Generate absolute minimum: "Just do these 3 things"
    - Simplified interface
    - Lowest friction
    - No guilt trips
"""

from dataclasses import dataclass

from src.core.logging import get_logger
from src.db.database import Database

logger = get_logger(__name__)


@dataclass
class RescueItem:
    """A single must-do item."""

    prospect_id: int
    prospect_name: str
    company_name: str
    action: str
    reason: str
    priority: int


class RescueEngine:
    """Zero-capacity crisis mode."""

    def __init__(self, db: Database):
        self.db = db

    def generate_rescue_list(self, max_items: int = 3) -> list[RescueItem]:
        """Generate minimal must-do list."""
        raise NotImplementedError("Phase 6, Step 6.8")

    def _prioritize_urgent(self) -> list[RescueItem]:
        """Find most urgent items."""
        raise NotImplementedError("Phase 6, Step 6.8")

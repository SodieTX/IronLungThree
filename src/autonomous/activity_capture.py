"""Activity capture - Automatic activity logging."""

from typing import Optional
from src.db.database import Database
from src.core.logging import get_logger

logger = get_logger(__name__)


def capture_email_activity(db: Database, message_id: str) -> Optional[int]:
    """Capture email as activity. Returns activity ID."""
    raise NotImplementedError("Phase 5")


def capture_calendar_activity(db: Database, event_id: str) -> Optional[int]:
    """Capture calendar event as activity."""
    raise NotImplementedError("Phase 5")

"""Activity capture - Automatic activity logging."""

from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Activity, ActivityType

logger = get_logger(__name__)


def capture_email_activity(db: Database, message_id: str) -> Optional[int]:
    """Capture email as activity. Returns activity ID if created, None if duplicate.

    Looks up whether an activity with this message_id has already been captured
    (stored in the notes field as 'message_id:<id>'). If not, creates a new
    EMAIL_RECEIVED activity record.

    Args:
        db: Database instance
        message_id: Unique email message identifier

    Returns:
        Activity ID if newly created, None if already captured
    """
    if not message_id:
        logger.warning("capture_email_activity called with empty message_id")
        return None

    conn = db._get_connection()

    # Check if already captured by searching notes for the message_id marker
    marker = f"message_id:{message_id}"
    existing = conn.execute(
        "SELECT id FROM activities WHERE notes LIKE ? LIMIT 1",
        (f"%{marker}%",),
    ).fetchone()

    if existing:
        logger.debug(
            "Email activity already captured",
            extra={"context": {"message_id": message_id, "activity_id": existing["id"]}},
        )
        return None

    # Create activity record
    activity = Activity(
        prospect_id=0,  # Will be updated by caller if prospect is matched
        activity_type=ActivityType.EMAIL_RECEIVED,
        notes=marker,
        created_by="system",
    )
    activity_id = db.create_activity(activity)
    logger.info(
        "Email activity captured",
        extra={"context": {"message_id": message_id, "activity_id": activity_id}},
    )
    return activity_id


def capture_calendar_activity(db: Database, event_id: str) -> Optional[int]:
    """Capture calendar event as activity. Returns activity ID if created, None if duplicate.

    Looks up whether an activity with this event_id has already been captured
    (stored in the notes field as 'event_id:<id>'). If not, creates a new
    DEMO_SCHEDULED activity record.

    Args:
        db: Database instance
        event_id: Unique calendar event identifier

    Returns:
        Activity ID if newly created, None if already captured
    """
    if not event_id:
        logger.warning("capture_calendar_activity called with empty event_id")
        return None

    conn = db._get_connection()

    # Check if already captured by searching notes for the event_id marker
    marker = f"event_id:{event_id}"
    existing = conn.execute(
        "SELECT id FROM activities WHERE notes LIKE ? LIMIT 1",
        (f"%{marker}%",),
    ).fetchone()

    if existing:
        logger.debug(
            "Calendar activity already captured",
            extra={"context": {"event_id": event_id, "activity_id": existing["id"]}},
        )
        return None

    # Create activity record
    activity = Activity(
        prospect_id=0,  # Will be updated by caller if prospect is matched
        activity_type=ActivityType.DEMO_SCHEDULED,
        notes=marker,
        created_by="system",
    )
    activity_id = db.create_activity(activity)
    logger.info(
        "Calendar activity captured",
        extra={"context": {"event_id": event_id, "activity_id": activity_id}},
    )
    return activity_id

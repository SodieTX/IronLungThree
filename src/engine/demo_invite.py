"""Demo invite coordination service.

Coordinates the full demo invite flow:
    - Creates a calendar event via OutlookClient
    - Sends a demo invite email using the demo_invite template
    - Logs a DEMO_SCHEDULED activity to the database
    - Returns a DemoInvite dataclass with all details

Works gracefully in offline mode (OutlookClient=None) by logging
the activity without sending calendar events or emails.

Usage:
    from src.engine.demo_invite import create_demo_invite

    invite = create_demo_invite(
        db=db,
        prospect_id=42,
        demo_datetime=datetime(2026, 2, 15, 14, 0),
        duration_minutes=30,
        outlook=outlook_client,
    )
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    Company,
    EngagementStage,
    Prospect,
)

logger = get_logger(__name__)

# Default sender info for demo invite emails
DEFAULT_SENDER = {
    "name": "Jeff",
    "title": "Account Executive",
    "company": "IronLung",
    "phone": "",
}


@dataclass
class DemoInvite:
    """Result of a demo invite operation.

    Attributes:
        prospect_id: Prospect who was invited
        prospect_name: Full name of the prospect
        company_name: Company name
        demo_datetime: Scheduled demo time
        duration_minutes: Demo duration in minutes
        calendar_event_id: Outlook calendar event ID (None if offline)
        email_sent: Whether the invite email was sent
        teams_link: Teams meeting link (None if offline)
        activity_id: Activity log entry ID
    """

    prospect_id: int
    prospect_name: str
    company_name: str
    demo_datetime: datetime
    duration_minutes: int
    calendar_event_id: Optional[str] = None
    email_sent: bool = False
    teams_link: Optional[str] = None
    activity_id: Optional[int] = None
    conflicts: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.conflicts is None:
            self.conflicts = []


@dataclass
class CalendarConflict:
    """A scheduling conflict with an existing calendar event."""

    subject: str
    start: str
    end: str


def check_calendar_conflicts(
    outlook: object,
    demo_datetime: datetime,
    duration_minutes: int,
) -> list[CalendarConflict]:
    """Check for calendar conflicts at the proposed demo time.

    Args:
        outlook: OutlookClient or OfflineOutlookClient
        demo_datetime: Proposed demo start time
        duration_minutes: Demo duration in minutes

    Returns:
        List of conflicting events (empty if no conflicts)
    """
    try:
        # Check events in a window around the proposed demo time
        start = demo_datetime - timedelta(minutes=30)
        end = demo_datetime + timedelta(minutes=duration_minutes + 30)

        events = outlook.get_events(start=start, end=end)  # type: ignore[attr-defined]
        if not events:
            return []

        demo_end = demo_datetime + timedelta(minutes=duration_minutes)
        conflicts: list[CalendarConflict] = []

        for evt in events:
            evt_start = getattr(evt, "start", None)
            evt_end = getattr(evt, "end", None)
            subject = getattr(evt, "subject", "Unknown event")

            if not evt_start or not evt_end:
                continue

            # Parse datetimes if they're strings
            if isinstance(evt_start, str):
                try:
                    evt_start = datetime.fromisoformat(evt_start)
                except ValueError:
                    continue
            if isinstance(evt_end, str):
                try:
                    evt_end = datetime.fromisoformat(evt_end)
                except ValueError:
                    continue

            # Check overlap: events overlap if one starts before the other ends
            if evt_start < demo_end and evt_end > demo_datetime:
                conflicts.append(
                    CalendarConflict(
                        subject=subject,
                        start=(
                            evt_start.strftime("%I:%M %p")
                            if isinstance(evt_start, datetime)
                            else str(evt_start)
                        ),
                        end=(
                            evt_end.strftime("%I:%M %p")
                            if isinstance(evt_end, datetime)
                            else str(evt_end)
                        ),
                    )
                )

        return conflicts

    except Exception as e:
        logger.debug(f"Calendar conflict check skipped: {e}")
        return []


def create_demo_invite(
    db: Database,
    prospect_id: int,
    demo_datetime: datetime,
    duration_minutes: int = 30,
    outlook: Optional[object] = None,
    sender: Optional[dict] = None,
) -> DemoInvite:
    """Create a demo invite with calendar event, email, and activity log.

    Coordinates the full demo scheduling flow:
    1. Look up prospect and company from the database
    2. Create a calendar event with Teams meeting link (if Outlook available)
    3. Send demo invite email (if Outlook available)
    4. Log a DEMO_SCHEDULED activity
    5. Return DemoInvite with all details

    When outlook is None, operates in offline mode: logs the activity
    but skips calendar and email operations.

    Args:
        db: Database instance
        prospect_id: ID of the prospect to invite
        demo_datetime: Scheduled demo date and time
        duration_minutes: Duration of the demo in minutes (default 30)
        outlook: OutlookClient instance (None for offline mode)
        sender: Sender info dict with name, title, company, phone keys

    Returns:
        DemoInvite with all details of the operation

    Raises:
        ValueError: If prospect or company not found
    """
    sender_info = sender or DEFAULT_SENDER

    # 1. Look up prospect and company
    prospect = db.get_prospect(prospect_id)
    if prospect is None:
        raise ValueError(f"Prospect not found: {prospect_id}")

    company = db.get_company(prospect.company_id)
    if company is None:
        raise ValueError(f"Company not found for prospect {prospect_id}")

    prospect_name = prospect.full_name
    company_name = company.name

    # Build result
    invite = DemoInvite(
        prospect_id=prospect_id,
        prospect_name=prospect_name,
        company_name=company_name,
        demo_datetime=demo_datetime,
        duration_minutes=duration_minutes,
    )

    # Look up prospect email for calendar invite attendee
    prospect_email: Optional[str] = None
    contact_methods = db.get_contact_methods(prospect.id or 0)
    for cm in contact_methods:
        if cm.type.value == "email":
            prospect_email = cm.value
            break

    # Check for calendar conflicts (informational, does not block)
    if outlook is not None:
        conflicts = check_calendar_conflicts(outlook, demo_datetime, duration_minutes)
        if conflicts:
            conflict_descs = [f"{c.subject} ({c.start} - {c.end})" for c in conflicts]
            invite.conflicts = conflict_descs
            logger.warning(
                f"Calendar conflicts detected for demo at {demo_datetime}: {conflict_descs}",
                extra={"context": {"conflicts": conflict_descs}},
            )

    # 2. Create calendar event (if Outlook available)
    if outlook is not None:
        calendar_event_id, teams_link = _create_calendar_event(
            outlook=outlook,
            prospect=prospect,
            company=company,
            demo_datetime=demo_datetime,
            duration_minutes=duration_minutes,
            prospect_email=prospect_email,
        )
        invite.calendar_event_id = calendar_event_id
        invite.teams_link = teams_link

        # 3. Send demo invite email (if Outlook available)
        email_sent = _send_invite_email(
            outlook=outlook,
            db=db,
            prospect=prospect,
            company=company,
            demo_datetime=demo_datetime,
            duration_minutes=duration_minutes,
            teams_link=teams_link or "",
            sender=sender_info,
        )
        invite.email_sent = email_sent
    else:
        logger.info(
            "Offline mode: skipping calendar event and email",
            extra={"context": {"prospect_id": prospect_id}},
        )

    # 4. Log DEMO_SCHEDULED activity
    activity_id = _log_demo_activity(
        db=db,
        prospect_id=prospect_id,
        demo_datetime=demo_datetime,
        duration_minutes=duration_minutes,
        teams_link=invite.teams_link,
        email_sent=invite.email_sent,
    )
    invite.activity_id = activity_id

    logger.info(
        f"Demo invite created for {prospect_name} at {company_name}",
        extra={
            "context": {
                "prospect_id": prospect_id,
                "demo_datetime": str(demo_datetime),
                "outlook_connected": outlook is not None,
            }
        },
    )

    return invite


def _create_calendar_event(
    outlook: object,
    prospect: Prospect,
    company: Company,
    demo_datetime: datetime,
    duration_minutes: int,
    prospect_email: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Create a calendar event with Teams meeting link.

    Args:
        outlook: OutlookClient instance
        prospect: Prospect record
        company: Company record
        demo_datetime: Demo start time
        duration_minutes: Demo duration
        prospect_email: Prospect's email address (added as attendee)

    Returns:
        Tuple of (event_id, teams_link), both None on failure
    """
    subject = f"Demo — {company.name} ({prospect.full_name})"

    attendees: list[str] = []
    if prospect_email:
        attendees.append(prospect_email)

    try:
        event_id, teams_link = outlook.create_event(  # type: ignore[attr-defined]
            subject=subject,
            start=demo_datetime,
            duration_minutes=duration_minutes,
            attendees=attendees or None,
            teams_meeting=True,
            body=f"Product demo for {company.name} with {prospect.full_name}",
        )

        logger.info(
            f"Calendar event created: {event_id}",
            extra={"context": {"event_id": event_id, "subject": subject, "teams_link": teams_link}},
        )
        return event_id, teams_link

    except Exception as e:
        logger.warning(
            f"Failed to create calendar event: {e}",
            extra={"context": {"error": str(e)}},
        )
        return None, None


def _send_invite_email(
    outlook: object,
    db: Database,
    prospect: Prospect,
    company: Company,
    demo_datetime: datetime,
    duration_minutes: int,
    teams_link: str,
    sender: dict,
) -> bool:
    """Send the demo invite email using the demo_invite template.

    Args:
        outlook: OutlookClient instance
        db: Database instance
        prospect: Prospect record
        company: Company record
        demo_datetime: Demo start time
        duration_minutes: Demo duration
        teams_link: Teams meeting link
        sender: Sender information dict

    Returns:
        True if email was sent successfully
    """
    try:
        from src.engine.templates import get_template_subject, render_template

        demo_info = {
            "date": demo_datetime,
            "duration_minutes": duration_minutes,
            "teams_link": teams_link,
        }

        # Render email body
        body_html = render_template(
            "demo_invite",
            prospect=prospect,
            company=company,
            demo=demo_info,
            sender=sender,
        )

        # Get subject line
        subject = get_template_subject(
            "demo_invite",
            prospect=prospect,
            company=company,
            demo=demo_info,
            sender=sender,
        )

        # Get primary email for prospect
        contact_methods = db.get_contact_methods(prospect.id or 0)
        email_address = None
        for cm in contact_methods:
            if cm.type.value == "email":
                email_address = cm.value
                break

        if not email_address:
            logger.warning(
                f"No email found for prospect {prospect.id}, skipping email send",
                extra={"context": {"prospect_id": prospect.id}},
            )
            return False

        outlook.send_email(  # type: ignore[attr-defined]
            to=email_address,
            subject=subject,
            body=body_html,
            html=True,
        )

        logger.info(
            f"Demo invite email sent to {email_address}",
            extra={"context": {"to": email_address, "subject": subject}},
        )
        return True

    except Exception as e:
        logger.warning(
            f"Failed to send demo invite email: {e}",
            extra={"context": {"error": str(e)}},
        )
        return False


def _log_demo_activity(
    db: Database,
    prospect_id: int,
    demo_datetime: datetime,
    duration_minutes: int,
    teams_link: Optional[str],
    email_sent: bool,
) -> int:
    """Log a DEMO_SCHEDULED activity to the database.

    Args:
        db: Database instance
        prospect_id: Prospect ID
        demo_datetime: Scheduled demo time
        duration_minutes: Demo duration
        teams_link: Teams link (if created)
        email_sent: Whether invite email was sent

    Returns:
        Activity ID
    """
    notes_parts = [
        f"Demo scheduled for {demo_datetime.strftime('%Y-%m-%d %H:%M')}",
        f"Duration: {duration_minutes} minutes",
    ]
    if teams_link:
        notes_parts.append(f"Teams link: {teams_link}")
    if email_sent:
        notes_parts.append("Invite email sent")
    else:
        notes_parts.append("No invite email sent (offline mode)")

    notes = ". ".join(notes_parts)

    activity = Activity(
        prospect_id=prospect_id,
        activity_type=ActivityType.DEMO_SCHEDULED,
        notes=notes,
        follow_up_set=demo_datetime,
        created_by="user",
    )

    activity_id = db.create_activity(activity)

    logger.info(
        f"DEMO_SCHEDULED activity logged: {activity_id}",
        extra={"context": {"activity_id": activity_id, "prospect_id": prospect_id}},
    )
    return activity_id

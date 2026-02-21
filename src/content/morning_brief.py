"""Morning brief generation.

Produces a 60-second readable memo with:
    - Pipeline summary (counts by population)
    - Today's calendar (meetings, demos, open calling windows)
    - Today's work queue (engaged follow-ups, unengaged queue)
    - Overdue items
    - Orphaned engaged (no follow-up date)
    - Overnight changes (if any)

Usage:
    from src.content.morning_brief import generate_morning_brief

    brief = generate_morning_brief(db)
    print(brief.full_text)
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Population

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

    # Structured data for GUI display
    population_counts: dict[str, int] = field(default_factory=dict)
    engaged_follow_ups: int = 0
    overdue_count: int = 0
    orphan_count: int = 0
    unengaged_queue_size: int = 0
    broken_count: int = 0
    total_prospects: int = 0

    # Calendar awareness
    calendar_text: str = ""
    calendar_events: int = 0
    demos_today: int = 0
    open_calling_minutes: int = 0

    # Phase 7: Proactive interrogation findings
    interrogation_text: str = ""
    interrogation_total: int = 0


def _get_calendar_section(today: date) -> tuple[str, int, int, int]:
    """Fetch today's calendar events and build the calendar brief section.

    Returns:
        (calendar_text, event_count, demo_count, open_calling_minutes)
    """
    try:
        from src.integrations.offline import get_outlook_client

        outlook = get_outlook_client()

        # Fetch events for today (8 AM to 6 PM local-ish window)
        start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=timezone.utc)
        events = outlook.get_events(start=start, end=end)

        if not events:
            return "No meetings on your calendar today.", 0, 0, 480  # 8 hrs

        lines: list[str] = []
        demo_count = 0
        total_meeting_minutes = 0

        for evt in events:
            # Handle both CalendarEvent dataclass and raw dict
            subject = getattr(evt, "subject", "") or ""
            evt_start = getattr(evt, "start", None)
            evt_end = getattr(evt, "end", None)
            attendees = getattr(evt, "attendees", []) or []
            teams_link = getattr(evt, "teams_link", None)

            # Format time
            time_str = ""
            duration_min = 0
            if evt_start and evt_end:
                if isinstance(evt_start, datetime):
                    time_str = evt_start.strftime("%I:%M %p")
                    duration_min = int((evt_end - evt_start).total_seconds() / 60)
                elif isinstance(evt_start, str):
                    try:
                        s = datetime.fromisoformat(evt_start)
                        e = datetime.fromisoformat(evt_end)
                        time_str = s.strftime("%I:%M %p")
                        duration_min = int((e - s).total_seconds() / 60)
                    except ValueError:
                        pass

            total_meeting_minutes += duration_min

            # Detect demos
            is_demo = "demo" in subject.lower()
            if is_demo:
                demo_count += 1

            dur_str = f" ({duration_min} min)" if duration_min else ""
            teams_str = " [Teams]" if teams_link else ""
            prefix = "DEMO" if is_demo else "Meeting"
            lines.append(f"  {time_str} — {prefix}: {subject}{dur_str}{teams_str}")

            # Show attendees for demos
            if is_demo and attendees:
                att_str = ", ".join(a[:30] for a in attendees[:3])
                lines.append(f"           with {att_str}")

        # Calculate open calling time (assume 8hr workday)
        workday_minutes = 480
        open_minutes = max(0, workday_minutes - total_meeting_minutes)

        summary = f"{len(events)} event(s) today"
        if demo_count:
            summary += f" ({demo_count} demo{'s' if demo_count > 1 else ''})"
        summary += f". ~{open_minutes // 60}h {open_minutes % 60}m open for calls."
        lines.insert(0, summary)

        return "\n".join(lines), len(events), demo_count, open_minutes

    except Exception as e:
        logger.debug(f"Calendar fetch skipped: {e}")
        return "", 0, 0, 0


def generate_morning_brief(db: Database) -> MorningBrief:
    """Generate morning brief content.

    Args:
        db: Database instance

    Returns:
        MorningBrief with all sections populated
    """
    today = date.today()
    today_str = today.strftime("%A, %B %d, %Y")

    # Get population counts
    pop_counts = db.get_population_counts()
    total = sum(pop_counts.values())

    # Format population summary
    population_counts: dict[str, int] = {}
    for pop in Population:
        count = pop_counts.get(pop, 0)
        population_counts[pop.value] = count

    pipeline_lines = []
    pipeline_lines.append(f"Total prospects: {total}")
    pipeline_lines.append("")

    active_pops = [
        (Population.ENGAGED, "Engaged"),
        (Population.UNENGAGED, "Unengaged"),
        (Population.BROKEN, "Broken"),
        (Population.PARKED, "Parked"),
    ]
    for pop, label in active_pops:
        count = pop_counts.get(pop, 0)
        if count > 0:
            pipeline_lines.append(f"  {label}: {count}")

    terminal_pops = [
        (Population.CLOSED_WON, "Closed Won"),
        (Population.LOST, "Lost"),
        (Population.DEAD_DNC, "DNC"),
        (Population.PARTNERSHIP, "Partnership"),
    ]
    terminal_counts = []
    for pop, label in terminal_pops:
        count = pop_counts.get(pop, 0)
        if count > 0:
            terminal_counts.append(f"{label}: {count}")
    if terminal_counts:
        pipeline_lines.append(f"  ({', '.join(terminal_counts)})")

    pipeline_summary = "\n".join(pipeline_lines)

    # Get overdue and orphan data
    from src.engine.cadence import get_orphaned_engaged, get_overdue

    overdue = get_overdue(db)
    overdue_count = len(overdue)
    orphans = get_orphaned_engaged(db)
    orphan_count = len(orphans)

    # Count engaged follow-ups for today
    conn = db._get_connection()
    today_iso = today.isoformat()
    engaged_today_rows = conn.execute(
        """SELECT COUNT(*) as cnt FROM prospects
           WHERE population = ? AND follow_up_date IS NOT NULL
           AND DATE(follow_up_date) = DATE(?)""",
        (Population.ENGAGED.value, today_iso),
    ).fetchone()
    engaged_follow_ups = engaged_today_rows["cnt"] if engaged_today_rows else 0

    # Get unengaged queue count
    unengaged_count = pop_counts.get(Population.UNENGAGED, 0)
    broken_count = pop_counts.get(Population.BROKEN, 0)

    # Build today's work section
    work_lines = []
    if engaged_follow_ups > 0:
        work_lines.append(f"Engaged follow-ups due today: {engaged_follow_ups}")
    if overdue_count > 0:
        work_lines.append(f"OVERDUE follow-ups: {overdue_count}")
        for p in overdue[:3]:
            try:
                fu_str = str(p.follow_up_date)[:10]
                fu_date = date.fromisoformat(fu_str)
                days = (today - fu_date).days
            except (ValueError, TypeError):
                days = 0
            work_lines.append(f"  - {p.full_name} ({days} days overdue)")
        if overdue_count > 3:
            work_lines.append(f"  ... and {overdue_count - 3} more")
    if unengaged_count > 0:
        work_lines.append(f"Unengaged prospects in queue: {unengaged_count}")
    if broken_count > 0:
        work_lines.append(f"Broken records needing research: {broken_count}")

    if not work_lines:
        work_lines.append("No follow-ups scheduled for today.")

    todays_work = "\n".join(work_lines)

    # Warnings
    warnings: list[str] = []
    if orphan_count > 0:
        warnings.append(f"{orphan_count} engaged prospect(s) have NO follow-up date set")
    if overdue_count >= 5:
        warnings.append(f"You have {overdue_count} overdue follow-ups")

    # Overnight changes (system activities from last 24 hours)
    overnight_lines = []
    yesterday = datetime(today.year, today.month, today.day, 0, 0, 0).strftime("%Y-%m-%d %H:%M:%S")
    system_activities = conn.execute(
        """SELECT a.*, p.first_name, p.last_name
           FROM activities a
           JOIN prospects p ON a.prospect_id = p.id
           WHERE a.created_by = 'system'
           AND a.created_at >= ?
           ORDER BY a.created_at DESC
           LIMIT 10""",
        (yesterday,),
    ).fetchall()

    if system_activities:
        for row in system_activities:
            name = f"{row['first_name']} {row['last_name']}"
            overnight_lines.append(f"  - {row['activity_type']}: {name}")
    else:
        overnight_lines.append("No overnight system activity.")

    overnight_changes = "\n".join(overnight_lines)

    # Calendar awareness
    calendar_text, calendar_events, demos_today, open_calling_minutes = _get_calendar_section(today)

    # Compose full text
    full_lines = [
        "IRONLUNG 3 - MORNING BRIEF",
        today_str,
        "",
        "--- PIPELINE ---",
        pipeline_summary,
        "",
    ]

    if calendar_text:
        full_lines.append("--- TODAY'S CALENDAR ---")
        full_lines.append(calendar_text)
        full_lines.append("")

    full_lines.append("--- TODAY'S WORK ---")
    full_lines.append(todays_work)
    full_lines.append("")

    # Deal momentum
    try:
        from src.engine.engagement_velocity import EngagementVelocity

        velocity = EngagementVelocity(db)
        vel_report = velocity.analyze()
        if vel_report.decelerating or vel_report.stalled:
            full_lines.append("--- DEAL MOMENTUM ---")
            full_lines.append(vel_report.summary)
            for deal in vel_report.stalled[:3]:
                full_lines.append(f"  ! {deal.prospect_name} ({deal.company_name}): {deal.detail}")
            for deal in vel_report.decelerating[:3]:
                full_lines.append(f"  ~ {deal.prospect_name} ({deal.company_name}): {deal.detail}")
            if vel_report.accelerating:
                for deal in vel_report.accelerating[:2]:
                    full_lines.append(
                        f"  + {deal.prospect_name} ({deal.company_name}): {deal.detail}"
                    )
            full_lines.append("")
    except Exception as e:
        logger.debug(f"Velocity analysis skipped: {e}")

    if warnings:
        full_lines.append("--- WARNINGS ---")
        for w in warnings:
            full_lines.append(f"! {w}")
        full_lines.append("")

    if system_activities:
        full_lines.append("--- OVERNIGHT ---")
        full_lines.append(overnight_changes)
        full_lines.append("")

    # Phase 7: Proactive card interrogation
    from src.ai.proactive_interrogation import interrogate_cards

    interrogation = interrogate_cards(db)
    interrogation_text = interrogation.findings_text
    if interrogation_text:
        full_lines.append("--- ANNE'S CARD REVIEW ---")
        full_lines.append(interrogation_text)
        full_lines.append("")

    total_today = engaged_follow_ups + overdue_count
    if total_today > 0:
        full_lines.append(f"You have {total_today} cards waiting. Ready? Let's go.")
    else:
        full_lines.append("Queue is clear. Time to hunt.")

    full_text = "\n".join(full_lines)

    return MorningBrief(
        date=today_str,
        pipeline_summary=pipeline_summary,
        todays_work=todays_work,
        overnight_changes=overnight_changes,
        warnings=warnings,
        full_text=full_text,
        population_counts=population_counts,
        engaged_follow_ups=engaged_follow_ups,
        overdue_count=overdue_count,
        orphan_count=orphan_count,
        unengaged_queue_size=unengaged_count,
        broken_count=broken_count,
        total_prospects=total,
        interrogation_text=interrogation_text,
        interrogation_total=interrogation.total_findings,
        calendar_text=calendar_text,
        calendar_events=calendar_events,
        demos_today=demos_today,
        open_calling_minutes=open_calling_minutes,
    )

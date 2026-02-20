"""Card story generator - Narrative context per prospect.

Generates narrative from notes:
    "You first called John in November. He was interested but said
    Q1 was too early. You parked him for March. March is here."
"""

from datetime import date, datetime

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Activity, ActivityType, IntelNugget, Population

logger = get_logger(__name__)


def generate_story(db: Database, prospect_id: int) -> str:
    """Generate narrative from prospect history.

    Reads activities, intel nuggets, and prospect state to build
    a human-readable story Anne can present.
    """
    full = db.get_prospect_full(prospect_id)
    if not full:
        return "No prospect data found."

    p = full.prospect
    company = full.company
    activities = full.activities  # most recent first
    nuggets = db.get_intel_nuggets(prospect_id)

    parts: list[str] = []

    # Identity
    name = p.full_name or "Unknown"
    company_name = company.name if company else "Unknown company"
    title_str = f", {p.title}" if p.title else ""
    parts.append(f"{name}{title_str} at {company_name}.")

    # Company context
    if company:
        details: list[str] = []
        if company.state:
            details.append(f"based in {company.state}")
        if company.loan_types:
            details.append(f"loan types: {company.loan_types}")
        if company.size:
            details.append(f"size: {company.size}")
        if details:
            parts.append(" ".join(details).capitalize() + ".")

    # Current status
    status = _describe_status(p.population, p.engagement_stage, p.parked_month)
    if status:
        parts.append(status)

    # Score
    if p.prospect_score > 0:
        parts.append(f"Score: {p.prospect_score}/100, confidence: {p.data_confidence}/100.")

    # Timeline summary
    if activities:
        timeline = _summarize_timeline(activities)
        if timeline:
            parts.append(timeline)

    # Key moments
    if activities:
        moments = _extract_key_moments(activities)
        if moments:
            parts.append("Key moments: " + " ".join(moments))

    # Intel nuggets
    if nuggets:
        intel_str = _format_intel(nuggets)
        if intel_str:
            parts.append(intel_str)

    # Attempt count
    if p.attempt_count > 0:
        parts.append(f"Total attempts: {p.attempt_count}.")

    # Follow-up
    if p.follow_up_date:
        fu_date = p.follow_up_date
        if isinstance(fu_date, str):
            parts.append(f"Follow-up set for {fu_date}.")
        else:
            parts.append(f"Follow-up set for {fu_date.strftime('%Y-%m-%d')}.")

    return " ".join(parts)


def _describe_status(
    population: Population,
    engagement_stage: object,
    parked_month: str | None,
) -> str:
    """Describe current prospect status in plain English."""
    labels = {
        Population.BROKEN: "Currently broken — missing contact info.",
        Population.UNENGAGED: "Unengaged — you're chasing, no interest shown yet.",
        Population.ENGAGED: "Engaged — they've shown interest.",
        Population.PARKED: "Parked",
        Population.DEAD_DNC: "Dead — Do Not Contact.",
        Population.LOST: "Lost — went with someone else.",
        Population.PARTNERSHIP: "Partnership contact — not a prospect.",
        Population.CLOSED_WON: "Closed won!",
    }
    status = labels.get(population, f"Status: {population.value}")

    if population == Population.PARKED and parked_month:
        status = f"Parked until {parked_month}."

    if population == Population.ENGAGED and engagement_stage:
        stage_val = (
            engagement_stage.value if hasattr(engagement_stage, "value") else str(engagement_stage)
        )
        stage_labels = {
            "pre_demo": "pre-demo",
            "demo_scheduled": "demo scheduled",
            "post_demo": "post-demo",
            "closing": "closing",
        }
        stage_str = stage_labels.get(stage_val, stage_val)
        status = f"Engaged — {stage_str}."

    return status


def _summarize_timeline(activities: list[Activity]) -> str:
    """Create timeline summary from activities."""
    if not activities:
        return ""

    # Activities are most-recent-first; reverse for chronological
    chronological = list(reversed(activities))

    first = chronological[0]
    last = chronological[-1]

    first_date = _format_activity_date(first.created_at)
    last_date = _format_activity_date(last.created_at)

    if len(activities) == 1:
        return f"One interaction on {first_date}: {first.activity_type.value}."

    return f"History: {len(activities)} interactions from {first_date} to {last_date}."


def _extract_key_moments(activities: list[Activity]) -> list[str]:
    """Find key moments in history."""
    moments: list[str] = []
    # Activities are most-recent-first
    for act in activities:
        date_str = _format_activity_date(act.created_at)

        if act.activity_type == ActivityType.STATUS_CHANGE:
            before = act.population_before.value if act.population_before else "?"
            after = act.population_after.value if act.population_after else "?"
            moments.append(f"{date_str}: moved {before} → {after}.")

        elif act.activity_type == ActivityType.DEMO_COMPLETED:
            moments.append(f"{date_str}: demo completed.")

        elif act.activity_type == ActivityType.DEMO_SCHEDULED:
            moments.append(f"{date_str}: demo scheduled.")

        elif act.outcome and act.outcome.value == "interested":
            moments.append(f"{date_str}: showed interest.")

        elif act.notes and len(act.notes) > 10:
            preview = act.notes[:80] + "..." if len(act.notes) > 80 else act.notes
            moments.append(f'{date_str}: "{preview}"')

        if len(moments) >= 5:
            break

    return moments


def _format_intel(nuggets: list[IntelNugget]) -> str:
    """Format intel nuggets into a readable string."""
    if not nuggets:
        return ""

    lines = ["Intel:"]
    for n in nuggets[:8]:
        category = n.category.value.replace("_", " ").title()
        lines.append(f"  {category}: {n.content}")
    return " ".join(lines)


def _format_activity_date(dt: datetime | str | None) -> str:
    """Format a datetime for display."""
    if dt is None:
        return "unknown date"
    if isinstance(dt, str):
        return dt[:10]
    if isinstance(dt, (datetime, date)):
        return dt.strftime("%b %d")
    return str(dt)[:10]

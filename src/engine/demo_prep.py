"""Demo preparation document generation.

Auto-generates demo prep from prospect data and notes:
    - Loan types
    - Company size
    - State/region
    - Pain points from notes
    - Competitive landscape from intel nuggets

Usage:
    from src.engine.demo_prep import generate_prep

    prep = generate_prep(db, prospect_id)
"""

import json
from dataclasses import dataclass
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    Company,
    IntelCategory,
    IntelNugget,
    Prospect,
)

logger = get_logger(__name__)


@dataclass
class DemoPrep:
    """Demo preparation document.

    Attributes:
        prospect_name: Prospect name
        company_name: Company name
        loan_types: Loan types they handle
        company_size: Company size
        state: State/region
        pain_points: Known pain points
        competitors: Competitors they're evaluating
        decision_timeline: Known timeline
        key_facts: Other relevant facts
        talking_points: Suggested talking points
        questions_to_ask: Questions to explore
        history_summary: Summary of interaction history
    """

    prospect_name: str
    company_name: str
    loan_types: list[str]
    company_size: Optional[str] = None
    state: Optional[str] = None
    pain_points: Optional[list[str]] = None
    competitors: Optional[list[str]] = None
    decision_timeline: Optional[str] = None
    key_facts: Optional[list[str]] = None
    talking_points: Optional[list[str]] = None
    questions_to_ask: Optional[list[str]] = None
    history_summary: Optional[str] = None


def generate_prep(db: Database, prospect_id: int) -> DemoPrep:
    """Generate demo preparation document.

    Pulls data from prospect, company, activities, and intel nuggets
    to build a comprehensive demo prep document.

    Args:
        db: Database instance
        prospect_id: Prospect ID

    Returns:
        DemoPrep document

    Raises:
        ValueError: If prospect or company not found
    """
    # Pull prospect
    prospect = db.get_prospect(prospect_id)
    if prospect is None:
        raise ValueError(f"Prospect not found: {prospect_id}")

    # Pull company
    company = db.get_company(prospect.company_id)
    if company is None:
        raise ValueError(f"Company not found for prospect {prospect_id}")

    # Pull activities and intel nuggets
    activities = db.get_activities(prospect_id)
    nuggets = db.get_intel_nuggets(prospect_id)

    # Parse loan types from company JSON field
    loan_types: list[str] = []
    if company.loan_types:
        try:
            parsed = json.loads(company.loan_types)
            if isinstance(parsed, list):
                loan_types = [str(lt) for lt in parsed]
        except (json.JSONDecodeError, TypeError):
            # If not valid JSON, treat as comma-separated string
            loan_types = [lt.strip() for lt in company.loan_types.split(",") if lt.strip()]

    # Extract intel from nuggets
    pain_points = _extract_pain_points(nuggets)
    competitors = _extract_competitors(nuggets)

    # Extract decision timeline from nuggets
    decision_timeline = None
    for nugget in nuggets:
        if nugget.category == IntelCategory.DECISION_TIMELINE:
            decision_timeline = nugget.content
            break

    # Extract key facts from nuggets
    key_facts = [
        nugget.content
        for nugget in nuggets
        if nugget.category == IntelCategory.KEY_FACT
    ]

    # Build the prep document
    prep = DemoPrep(
        prospect_name=prospect.full_name,
        company_name=company.name,
        loan_types=loan_types,
        company_size=company.size,
        state=company.state,
        pain_points=pain_points or None,
        competitors=competitors or None,
        decision_timeline=decision_timeline,
        key_facts=key_facts or None,
        history_summary=_summarize_history(activities),
    )

    # Generate talking points based on all collected data
    prep.talking_points = _generate_talking_points(prep)

    # Generate questions to ask
    prep.questions_to_ask = _generate_questions(prep)

    logger.info(
        f"Demo prep generated for {prospect.full_name} at {company.name}",
        extra={
            "context": {
                "prospect_id": prospect_id,
                "pain_points_count": len(pain_points),
                "competitors_count": len(competitors),
                "activities_count": len(activities),
            }
        },
    )

    return prep


def _extract_pain_points(nuggets: list[IntelNugget]) -> list[str]:
    """Extract pain points from intel nuggets.

    Filters nuggets by PAIN_POINT category and returns their content.

    Args:
        nuggets: List of intel nuggets

    Returns:
        List of pain point strings
    """
    return [
        nugget.content
        for nugget in nuggets
        if nugget.category == IntelCategory.PAIN_POINT
    ]


def _extract_competitors(nuggets: list[IntelNugget]) -> list[str]:
    """Extract competitor mentions from intel nuggets.

    Filters nuggets by COMPETITOR category and returns unique competitor names.

    Args:
        nuggets: List of intel nuggets

    Returns:
        List of competitor name strings (deduplicated)
    """
    seen: set[str] = set()
    competitors: list[str] = []
    for nugget in nuggets:
        if nugget.category == IntelCategory.COMPETITOR:
            normalized = nugget.content.strip().lower()
            if normalized not in seen:
                seen.add(normalized)
                competitors.append(nugget.content.strip())
    return competitors


def _generate_talking_points(prep: DemoPrep) -> list[str]:
    """Generate talking points based on prep data.

    Creates contextual talking points from available information
    about the prospect's company, pain points, and competitive landscape.

    Args:
        prep: DemoPrep document with collected data

    Returns:
        List of talking point strings
    """
    points: list[str] = []

    # Loan type talking points
    if prep.loan_types:
        loan_str = ", ".join(prep.loan_types)
        points.append(f"Discuss our capabilities for {loan_str} loan types")

    # Company size talking points
    if prep.company_size:
        points.append(f"Tailor demo to {prep.company_size}-sized operation")

    # Pain point talking points
    if prep.pain_points:
        for pain in prep.pain_points:
            points.append(f"Address pain point: {pain}")

    # Competitor talking points
    if prep.competitors:
        comp_str = ", ".join(prep.competitors)
        points.append(f"Differentiate vs. {comp_str}")

    # Decision timeline
    if prep.decision_timeline:
        points.append(f"Timeline: {prep.decision_timeline}")

    # State/region
    if prep.state:
        points.append(f"Reference {prep.state} market knowledge")

    # If no specific points, add generic ones
    if not points:
        points.append("Focus on core platform walkthrough")
        points.append("Ask about their current workflow and pain points")

    return points


def _generate_questions(prep: DemoPrep) -> list[str]:
    """Generate questions to ask during the demo.

    Creates contextual questions based on gaps in our knowledge.

    Args:
        prep: DemoPrep document with collected data

    Returns:
        List of question strings
    """
    questions: list[str] = []

    if not prep.loan_types:
        questions.append("What loan types does your team focus on?")

    if not prep.company_size:
        questions.append("How large is your team?")

    if not prep.decision_timeline:
        questions.append("What's your timeline for making a decision?")

    if not prep.competitors:
        questions.append("Are you evaluating any other solutions?")

    if not prep.pain_points:
        questions.append("What are the biggest challenges in your current workflow?")

    # Always good to ask
    questions.append("Who else would be involved in the decision?")

    return questions


def _summarize_history(activities: list[Activity]) -> str:
    """Summarize interaction history from activities.

    Creates a concise summary of the interaction history,
    including counts of different activity types and key notes.

    Args:
        activities: List of Activity records (most recent first)

    Returns:
        Summary string of interaction history
    """
    if not activities:
        return "No prior interaction history."

    # Count activity types
    type_counts: dict[str, int] = {}
    for activity in activities:
        type_name = activity.activity_type.value
        type_counts[type_name] = type_counts.get(type_name, 0) + 1

    # Build summary parts
    parts: list[str] = []
    total = len(activities)
    parts.append(f"{total} total interaction{'s' if total != 1 else ''}")

    # Summarize by type
    type_summaries: list[str] = []
    for atype, count in sorted(type_counts.items()):
        type_summaries.append(f"{count} {atype}")
    if type_summaries:
        parts.append(f"({', '.join(type_summaries)})")

    # Include most recent activity note
    most_recent = activities[0]
    if most_recent.notes:
        parts.append(f"Last note: {most_recent.notes}")

    return ". ".join(parts)

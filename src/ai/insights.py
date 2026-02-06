"""Prospect insights - Per-prospect strategic suggestions.

Generates:
    - Best approach based on history
    - Likely objections
    - Competitive vulnerabilities
    - Timing recommendations
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import (
    ActivityType,
    EngagementStage,
    IntelCategory,
    Population,
)

logger = get_logger(__name__)


@dataclass
class ProspectInsights:
    """Strategic insights for prospect."""

    prospect_id: int
    best_approach: str
    likely_objections: list[str]
    competitive_vulnerabilities: list[str]
    timing_recommendation: Optional[str] = None
    confidence: float = 0.0


def generate_insights(db: Database, prospect_id: int) -> ProspectInsights:
    """Generate strategic insights for prospect.

    Builds a picture from:
    - Activity history (what's worked, what hasn't)
    - Intel nuggets (pain points, competitors, timelines)
    - Current engagement stage
    - Learning engine patterns from similar deals

    Args:
        db: Database instance
        prospect_id: Prospect to analyze

    Returns:
        ProspectInsights with strategic suggestions
    """
    prospect_full = db.get_prospect_full(prospect_id)
    if not prospect_full:
        return ProspectInsights(
            prospect_id=prospect_id,
            best_approach="No data available for this prospect.",
            likely_objections=[],
            competitive_vulnerabilities=[],
            confidence=0.0,
        )

    prospect = prospect_full.prospect
    activities = prospect_full.activities
    nuggets = db.get_intel_nuggets(prospect_id)

    # Determine best approach based on activity history
    best_approach = _determine_best_approach(prospect, activities)

    # Identify likely objections from intel and patterns
    likely_objections = _identify_objections(prospect, nuggets, activities)

    # Find competitive vulnerabilities
    competitive_vulns = _find_competitive_vulnerabilities(nuggets, activities)

    # Timing recommendation
    timing = _timing_recommendation(prospect, activities)

    # Confidence based on data density
    data_points = len(activities) + len(nuggets)
    if data_points >= 10:
        confidence = 0.8
    elif data_points >= 5:
        confidence = 0.6
    elif data_points >= 2:
        confidence = 0.4
    else:
        confidence = 0.2

    insights = ProspectInsights(
        prospect_id=prospect_id,
        best_approach=best_approach,
        likely_objections=likely_objections,
        competitive_vulnerabilities=competitive_vulns,
        timing_recommendation=timing,
        confidence=confidence,
    )

    logger.info(
        "Prospect insights generated",
        extra={
            "context": {
                "prospect_id": prospect_id,
                "confidence": confidence,
                "objections": len(likely_objections),
                "vulnerabilities": len(competitive_vulns),
            }
        },
    )

    return insights


def _determine_best_approach(prospect, activities) -> str:
    """Determine the best approach based on history."""
    if not activities:
        if prospect.preferred_contact_method == "email":
            return "No prior contact. Prospect prefers email — lead with a concise, value-focused email."
        elif prospect.preferred_contact_method == "phone":
            return "No prior contact. Prospect prefers phone — call with a clear 30-second hook."
        return "No prior contact. Start with a call to establish rapport, follow up by email."

    # Analyze what's gotten responses
    call_count = 0
    call_connects = 0
    email_count = 0
    email_replies = 0

    for act in activities:
        if act.activity_type == ActivityType.CALL:
            call_count += 1
            if act.outcome and act.outcome.value in ("spoke_with", "interested", "demo_set"):
                call_connects += 1
        elif act.activity_type == ActivityType.VOICEMAIL:
            call_count += 1
        elif act.activity_type == ActivityType.EMAIL_SENT:
            email_count += 1
        elif act.activity_type == ActivityType.EMAIL_RECEIVED:
            email_replies += 1

    # Determine which channel works
    call_rate = call_connects / call_count if call_count > 0 else 0
    email_rate = email_replies / email_count if email_count > 0 else 0

    if prospect.engagement_stage == EngagementStage.CLOSING:
        return "In closing stage. Focus on removing obstacles and getting the contract signed."
    elif prospect.engagement_stage == EngagementStage.POST_DEMO:
        return "Post-demo. Follow up on specific questions from the demo. Ask about next steps and timeline."
    elif prospect.engagement_stage == EngagementStage.DEMO_SCHEDULED:
        return "Demo upcoming. Prepare by reviewing all intel. Confirm attendees and customize the demo."
    elif prospect.engagement_stage == EngagementStage.PRE_DEMO:
        if call_rate > email_rate and call_count >= 2:
            return "Pre-demo, phone works best with this contact. Call to push for the demo."
        elif email_rate > 0:
            return "Pre-demo, email gets responses. Send a targeted email with a clear demo CTA."
        return "Pre-demo. Mix calls and emails — try to get the demo booked."

    # Unengaged or other
    if prospect.attempt_count >= 4 and call_connects == 0:
        return (
            f"After {prospect.attempt_count} attempts with no connection, "
            f"try a different approach: LinkedIn, referral, or different time of day."
        )
    elif call_rate > email_rate:
        return "Phone has been more effective. Call during business hours with a prepared hook."
    elif email_rate > call_rate:
        return "Email gets better responses. Lead with email, follow up with a call 2 days later."

    return "Mix phone and email. Call first, follow up with email same day."


def _identify_objections(prospect, nuggets, activities) -> list[str]:
    """Identify likely objections from data."""
    objections = []

    # From intel nuggets
    pain_points = [n for n in nuggets if n.category == IntelCategory.PAIN_POINT]
    for pp in pain_points:
        objections.append(f"Known pain point: {pp.content}")

    # From activity notes — look for objection keywords
    objection_keywords = {
        "price": "Pricing concerns raised",
        "expensive": "Cost sensitivity noted",
        "budget": "Budget constraints mentioned",
        "contract": "Existing contract may be a barrier",
        "timing": "Timing concerns raised",
        "not ready": "Not ready to make a change",
        "stakeholder": "Multiple stakeholders need buy-in",
        "security": "Security requirements a concern",
        "migration": "Data migration concerns",
    }

    found_objections: set[str] = set()
    for act in activities:
        if act.notes:
            notes_lower = act.notes.lower()
            for keyword, desc in objection_keywords.items():
                if keyword in notes_lower and desc not in found_objections:
                    objections.append(desc)
                    found_objections.add(desc)

    # From competitor intel
    competitors = [n for n in nuggets if n.category == IntelCategory.COMPETITOR]
    if competitors:
        objections.append(
            f"Competitor in play: {competitors[0].content}. " f"Expect comparison objections."
        )

    # Timeline pressure
    timelines = [n for n in nuggets if n.category == IntelCategory.DECISION_TIMELINE]
    if timelines:
        objections.append(f"Decision timeline: {timelines[0].content}")

    return objections


def _find_competitive_vulnerabilities(nuggets, activities) -> list[str]:
    """Find competitive vulnerabilities from intel."""
    vulns = []

    competitors = [n for n in nuggets if n.category == IntelCategory.COMPETITOR]
    for comp in competitors:
        content_lower = comp.content.lower()
        # Identify specific competitors and their known weaknesses
        if any(c in content_lower for c in ("encompass", "calyx")):
            vulns.append(
                f"Using legacy LOS ({comp.content}). "
                f"Highlight modern architecture, API-first approach, faster onboarding."
            )
        elif any(c in content_lower for c in ("loanpro", "loan pro")):
            vulns.append(
                f"Comparing with LoanPro ({comp.content}). "
                f"Emphasize Nexys differentiators: borrower portal, compliance tools."
            )
        elif any(c in content_lower for c in ("fiserv", "black knight", "ice mortgage")):
            vulns.append(
                f"Enterprise competitor ({comp.content}). "
                f"Focus on flexibility, implementation speed, and cost efficiency."
            )
        else:
            vulns.append(
                f"Competitor mentioned: {comp.content}. "
                f"Research their weaknesses and prepare differentiators."
            )

    # If no competitor intel, note the gap
    if not competitors:
        # Check activity notes for competitor mentions
        for act in activities:
            if act.notes and any(
                c in act.notes.lower()
                for c in ("competitor", "comparing", "also looking at", "evaluating")
            ):
                vulns.append(
                    "Competitor involvement suspected from notes. "
                    "Probe for specifics on next contact."
                )
                break

    return vulns


def _timing_recommendation(prospect, activities) -> Optional[str]:
    """Generate timing recommendation."""
    today = date.today()

    if prospect.follow_up_date:
        try:
            fu_str = str(prospect.follow_up_date)[:10]
            fu_date = date.fromisoformat(fu_str)
            days_until = (fu_date - today).days
            if days_until < 0:
                return f"Follow-up is {abs(days_until)} days OVERDUE. Contact immediately."
            elif days_until == 0:
                return "Follow-up is TODAY. Make this your priority."
            elif days_until <= 2:
                return f"Follow-up in {days_until} day(s). Prep your approach now."
            else:
                return f"Follow-up scheduled for {fu_str} ({days_until} days out)."
        except (ValueError, TypeError):
            pass

    if prospect.parked_month:
        return f"Parked until {prospect.parked_month}. Will auto-reactivate."

    if prospect.population == Population.ENGAGED and not prospect.follow_up_date:
        return "ENGAGED with no follow-up date — this is an orphan. Set a date immediately."

    if prospect.population == Population.UNENGAGED:
        if prospect.attempt_count == 0:
            return "Never contacted. Ready for first attempt."
        else:
            return f"Unengaged after {prospect.attempt_count} attempts. System cadence will schedule next."

    return None

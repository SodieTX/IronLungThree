"""Contact analyzer - Engagement patterns across companies.

Analyzes:
    - Which contacts are advancing
    - Which are stalling
    - Multi-contact coordination at same company
"""

from dataclasses import dataclass
from datetime import date, timedelta

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import EngagementStage, Population

logger = get_logger(__name__)


@dataclass
class CompanyAnalysis:
    """Analysis of contacts at a company."""

    company_id: int
    company_name: str
    total_contacts: int
    advancing_contacts: list[int]
    stalling_contacts: list[int]
    recommendations: list[str]


def analyze_company(db: Database, company_id: int) -> CompanyAnalysis:
    """Analyze engagement patterns at company.

    Looks at all prospects at the company and determines which are
    advancing (recent activity, stage progression) vs. stalling
    (no activity, stuck in stage).

    Args:
        db: Database instance
        company_id: Company to analyze

    Returns:
        CompanyAnalysis with engagement patterns and recommendations
    """
    conn = db._get_connection()
    company = db.get_company(company_id)
    company_name = company.name if company else "Unknown"

    # Get all prospects at this company (exclude terminal states)
    prospects = conn.execute(
        """SELECT p.id, p.first_name, p.last_name, p.population,
                  p.engagement_stage, p.prospect_score, p.follow_up_date,
                  p.last_contact_date, p.attempt_count
           FROM prospects p
           WHERE p.company_id = ?
             AND p.population NOT IN (?, ?)
           ORDER BY p.prospect_score DESC""",
        (company_id, Population.DEAD_DNC.value, Population.CLOSED_WON.value),
    ).fetchall()

    if not prospects:
        return CompanyAnalysis(
            company_id=company_id,
            company_name=company_name,
            total_contacts=0,
            advancing_contacts=[],
            stalling_contacts=[],
            recommendations=["No active contacts at this company."],
        )

    today = date.today()
    stale_cutoff = (today - timedelta(days=14)).isoformat()
    advancing = []
    stalling = []

    for p in prospects:
        pid = p["id"]
        pop = p["population"]

        # Check recent activity
        last_activity = conn.execute(
            """SELECT MAX(created_at) as last_act
               FROM activities
               WHERE prospect_id = ?""",
            (pid,),
        ).fetchone()

        has_recent_activity = False
        if last_activity and last_activity["last_act"]:
            try:
                act_str = str(last_activity["last_act"])[:10]
                act_date = date.fromisoformat(act_str)
                has_recent_activity = act_date >= date.fromisoformat(stale_cutoff)
            except (ValueError, TypeError):
                pass

        # Check stage progression (any stage change in last 30 days)
        stage_changes = conn.execute(
            """SELECT COUNT(*) as cnt
               FROM activities
               WHERE prospect_id = ?
                 AND activity_type = 'status_change'
                 AND created_at >= ?""",
            (pid, (today - timedelta(days=30)).isoformat()),
        ).fetchone()
        has_stage_movement = stage_changes and stage_changes["cnt"] > 0

        # Classify
        if pop == Population.ENGAGED.value and (has_recent_activity or has_stage_movement):
            advancing.append(pid)
        elif pop == Population.ENGAGED.value and not has_recent_activity:
            stalling.append(pid)
        elif pop == Population.UNENGAGED.value and has_recent_activity:
            advancing.append(pid)
        elif pop == Population.UNENGAGED.value and not has_recent_activity:
            stalling.append(pid)
        elif pop == Population.LOST.value:
            stalling.append(pid)
        else:
            stalling.append(pid)

    # Generate recommendations
    recommendations = []
    total = len(prospects)

    if len(advancing) > 0 and len(stalling) > 0:
        recommendations.append(
            f"{len(advancing)} of {total} contacts advancing, "
            f"{len(stalling)} stalling. Focus on the movers."
        )

    if len(stalling) == total:
        recommendations.append("All contacts stalling. Consider a new angle or different champion.")

    # Multi-contact coordination
    engaged_count = sum(1 for p in prospects if p["population"] == Population.ENGAGED.value)
    if engaged_count > 1:
        recommendations.append(
            f"Multiple engaged contacts ({engaged_count}). "
            f"Coordinate messaging to avoid conflicting signals."
        )

    if engaged_count == 0 and total > 0:
        unengaged_count = sum(1 for p in prospects if p["population"] == Population.UNENGAGED.value)
        if unengaged_count > 0:
            recommendations.append(
                f"{unengaged_count} unengaged contacts. "
                f"No champion yet — push for a demo with the highest-scored contact."
            )

    # Check for lost contacts — learn from them
    lost_at_company = conn.execute(
        """SELECT COUNT(*) as cnt FROM prospects
           WHERE company_id = ? AND population = ?""",
        (company_id, Population.LOST.value),
    ).fetchone()
    if lost_at_company and lost_at_company["cnt"] > 0:
        recommendations.append(
            f"{lost_at_company['cnt']} contact(s) previously lost at this company. "
            f"Review loss reasons before engaging new contacts."
        )

    if not recommendations:
        recommendations.append("Company engagement looks healthy.")

    analysis = CompanyAnalysis(
        company_id=company_id,
        company_name=company_name,
        total_contacts=total,
        advancing_contacts=advancing,
        stalling_contacts=stalling,
        recommendations=recommendations,
    )

    logger.info(
        "Company analysis complete",
        extra={
            "context": {
                "company_id": company_id,
                "company_name": company_name,
                "total": total,
                "advancing": len(advancing),
                "stalling": len(stalling),
            }
        },
    )

    return analysis


def find_stalling_patterns(db: Database) -> list[dict]:
    """Find prospects with stalling engagement patterns.

    Returns prospects that are engaged but show signs of stalling:
    - No activity in 14+ days
    - No stage progression in 30+ days
    - Follow-up date passed without action

    Returns:
        List of dicts with prospect_id, name, company, issue, days_stale
    """
    conn = db._get_connection()
    today = date.today()
    stale_cutoff = (today - timedelta(days=14)).isoformat()

    # Engaged prospects with no recent activity
    rows = conn.execute(
        """SELECT p.id, p.first_name, p.last_name, p.engagement_stage,
                  p.follow_up_date, c.name as company_name,
                  MAX(a.created_at) as last_activity
           FROM prospects p
           LEFT JOIN companies c ON p.company_id = c.id
           LEFT JOIN activities a ON a.prospect_id = p.id
           WHERE p.population = ?
           GROUP BY p.id
           HAVING last_activity IS NULL OR DATE(last_activity) < DATE(?)""",
        (Population.ENGAGED.value, stale_cutoff),
    ).fetchall()

    stalling = []
    for row in rows:
        if row["last_activity"]:
            try:
                last_str = str(row["last_activity"])[:10]
                last_date = date.fromisoformat(last_str)
                days_stale = (today - last_date).days
            except (ValueError, TypeError):
                days_stale = 14
        else:
            days_stale = 14

        name = f"{row['first_name']} {row['last_name']}".strip()
        stage = row["engagement_stage"] or "unknown"

        issue = f"Engaged ({stage}), no activity for {days_stale} days"
        if row["follow_up_date"]:
            try:
                fu_str = str(row["follow_up_date"])[:10]
                fu_date = date.fromisoformat(fu_str)
                if fu_date < today:
                    issue += f", follow-up overdue since {fu_str}"
            except (ValueError, TypeError):
                pass

        stalling.append(
            {
                "prospect_id": row["id"],
                "name": name,
                "company": row["company_name"] or "Unknown",
                "issue": issue,
                "days_stale": days_stale,
            }
        )

    logger.info(
        "Stalling pattern scan complete",
        extra={"context": {"stalling_count": len(stalling)}},
    )

    return stalling

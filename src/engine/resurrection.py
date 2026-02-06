"""Dead lead resurrection audit - Review cold leads for re-engagement.

Step 7.9: Identifies prospects that have been dead/lost for 12+ months
and may be worth re-engaging. Time changes things — contracts expire,
new decision makers arrive, budgets reset.

Usage:
    from src.engine.resurrection import find_resurrection_candidates

    candidates = find_resurrection_candidates(db)
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import LostReason, Population

logger = get_logger(__name__)


@dataclass
class ResurrectionCandidate:
    """A lost/dead lead that might be worth re-engaging.

    Attributes:
        prospect_id: Prospect ID
        prospect_name: Full name
        company_name: Company name
        population: Current population (lost or dead)
        reason: Why they were lost/dead
        months_dormant: How long since they were marked
        original_score: Their score before being lost
        rationale: Why they might be worth re-engaging
    """

    prospect_id: int
    prospect_name: str
    company_name: str
    population: str
    reason: Optional[str] = None
    months_dormant: int = 0
    original_score: int = 0
    rationale: str = ""


def find_resurrection_candidates(
    db: Database,
    min_months_dormant: int = 12,
    min_original_score: int = 30,
) -> list[ResurrectionCandidate]:
    """Find lost leads that may be worth re-engaging.

    Criteria:
    - Lost 12+ months ago (contracts may have expired)
    - NOT DNC (those are permanent and absolute)
    - Had a reasonable score before being lost
    - Lost for reasons that may have changed (timing, budget, competitor)

    Args:
        db: Database instance
        min_months_dormant: Minimum months since lost (default 12)
        min_original_score: Minimum original score to consider (default 30)

    Returns:
        List of ResurrectionCandidate sorted by original score (highest first)
    """
    conn = db._get_connection()
    today = date.today()
    cutoff = (today - timedelta(days=min_months_dormant * 30)).isoformat()

    # NEVER resurrect DNC — that's absolute and permanent
    rows = conn.execute(
        """SELECT p.id, p.first_name, p.last_name, p.population,
                  p.lost_reason, p.lost_competitor, p.lost_date,
                  p.prospect_score, p.notes, c.name as company_name
           FROM prospects p
           LEFT JOIN companies c ON p.company_id = c.id
           WHERE p.population = ?
             AND p.lost_date IS NOT NULL
             AND DATE(p.lost_date) < DATE(?)
             AND p.prospect_score >= ?
           ORDER BY p.prospect_score DESC""",
        (Population.LOST.value, cutoff, min_original_score),
    ).fetchall()

    candidates = []
    for row in rows:
        lost_date_str = str(row["lost_date"])[:10] if row["lost_date"] else None
        months_dormant = 0
        if lost_date_str:
            try:
                lost_date = date.fromisoformat(lost_date_str)
                months_dormant = (today - lost_date).days // 30
            except (ValueError, TypeError):
                months_dormant = min_months_dormant

        # Generate rationale based on why they were lost
        lost_reason = row["lost_reason"]
        rationale = _generate_rationale(lost_reason, row["lost_competitor"], months_dormant)

        name = f"{row['first_name']} {row['last_name']}".strip()
        reason_display = lost_reason or "unknown"
        if row["lost_competitor"]:
            reason_display += f" (to {row['lost_competitor']})"

        candidates.append(
            ResurrectionCandidate(
                prospect_id=row["id"],
                prospect_name=name,
                company_name=row["company_name"] or "Unknown",
                population=row["population"],
                reason=reason_display,
                months_dormant=months_dormant,
                original_score=row["prospect_score"],
                rationale=rationale,
            )
        )

    logger.info(
        "Resurrection audit complete",
        extra={
            "context": {
                "candidates_found": len(candidates),
                "min_months": min_months_dormant,
                "min_score": min_original_score,
            }
        },
    )

    return candidates


def _generate_rationale(
    lost_reason: Optional[str],
    lost_competitor: Optional[str],
    months_dormant: int,
) -> str:
    """Generate a rationale for why this lead might be worth re-engaging."""
    parts = []

    if months_dormant >= 24:
        parts.append(f"Dormant {months_dormant} months — a lot can change in 2+ years.")
    elif months_dormant >= 18:
        parts.append(
            f"Dormant {months_dormant} months — budget cycles and contracts may have reset."
        )
    else:
        parts.append(f"Dormant {months_dormant} months.")

    if lost_reason:
        reason_lower = lost_reason.lower()
        if "timing" in reason_lower:
            parts.append("Lost to timing — the timing may now be right.")
        elif "budget" in reason_lower:
            parts.append("Lost to budget — new fiscal year may have new budget.")
        elif "competitor" in reason_lower or "lost_to_competitor" in reason_lower:
            if lost_competitor:
                parts.append(
                    f"Lost to {lost_competitor} — check if they're still happy "
                    f"or if the competitor contract is expiring."
                )
            else:
                parts.append("Lost to competitor — their contract may be expiring soon.")
        elif "not_buying" in reason_lower:
            parts.append("Wasn't buying then — business needs evolve.")
        elif "out_of_business" in reason_lower:
            parts.append("Was out of business — verify before attempting contact.")

    if not parts:
        parts.append("Review notes and consider a fresh approach.")

    return " ".join(parts)


def generate_resurrection_report(db: Database) -> str:
    """Generate a human-readable resurrection audit report.

    Returns:
        Formatted report text
    """
    candidates = find_resurrection_candidates(db)

    if not candidates:
        return "No resurrection candidates found. All lost leads are either too recent or too low-scored."

    lines = [
        "DEAD LEAD RESURRECTION AUDIT",
        f"Found {len(candidates)} leads worth reviewing:\n",
    ]

    for c in candidates:
        lines.append(f"  {c.prospect_name} ({c.company_name})")
        lines.append(
            f"    Score: {c.original_score} | Dormant: {c.months_dormant} months | Reason: {c.reason}"
        )
        lines.append(f"    {c.rationale}")
        lines.append("")

    lines.append(
        "To resurrect: Move the prospect back to Unengaged. "
        "Their history and notes are preserved."
    )

    return "\n".join(lines)

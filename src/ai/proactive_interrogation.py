"""Proactive card interrogation - Anne reviews cards during brief generation.

Step 7.7: Anne reviews cards and identifies:
    - Orphans (engaged with no follow-up date)
    - Stale engaged leads (2+ weeks no activity)
    - High-score/low-confidence prospects
    - Follow-up dates that already passed

Findings surface in morning brief and when a card comes up.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Population

logger = get_logger(__name__)


@dataclass
class CardFinding:
    """A single finding from proactive interrogation.

    Attributes:
        prospect_id: Prospect ID
        prospect_name: Prospect name
        company_name: Company name
        finding_type: Type of finding
        description: Human-readable description
        severity: high, medium, low
        suggested_action: What Anne suggests doing
    """

    prospect_id: int
    prospect_name: str
    company_name: str
    finding_type: str
    description: str
    severity: str = "medium"
    suggested_action: str = ""


@dataclass
class InterrogationReport:
    """Results from proactive card interrogation.

    Attributes:
        orphans: Engaged prospects with no follow-up date
        stale_leads: Engaged leads with no activity in 2+ weeks
        data_concerns: High-score prospects with low data confidence
        overdue_followups: Follow-up dates that already passed
        findings_text: Human-readable summary for morning brief
    """

    orphans: list[CardFinding] = field(default_factory=list)
    stale_leads: list[CardFinding] = field(default_factory=list)
    data_concerns: list[CardFinding] = field(default_factory=list)
    overdue_followups: list[CardFinding] = field(default_factory=list)

    @property
    def total_findings(self) -> int:
        """Total number of findings."""
        return (
            len(self.orphans)
            + len(self.stale_leads)
            + len(self.data_concerns)
            + len(self.overdue_followups)
        )

    @property
    def has_urgent(self) -> bool:
        """Whether there are high-severity findings."""
        all_findings = self.orphans + self.stale_leads + self.data_concerns + self.overdue_followups
        return any(f.severity == "high" for f in all_findings)

    @property
    def findings_text(self) -> str:
        """Generate human-readable findings for morning brief."""
        if self.total_findings == 0:
            return ""

        lines = [f"Anne reviewed your cards and found {self.total_findings} items:\n"]

        if self.orphans:
            lines.append(f"  Orphaned engaged ({len(self.orphans)}) — need follow-up dates:")
            for f in self.orphans[:3]:
                lines.append(f"    {f.prospect_name} ({f.company_name}): {f.suggested_action}")
            if len(self.orphans) > 3:
                lines.append(f"    ... and {len(self.orphans) - 3} more")

        if self.overdue_followups:
            lines.append(f"  Overdue ({len(self.overdue_followups)}):")
            for f in self.overdue_followups[:3]:
                lines.append(f"    {f.prospect_name}: {f.description}")
            if len(self.overdue_followups) > 3:
                lines.append(f"    ... and {len(self.overdue_followups) - 3} more")

        if self.stale_leads:
            lines.append(f"  Going stale ({len(self.stale_leads)}):")
            for f in self.stale_leads[:3]:
                lines.append(f"    {f.prospect_name}: {f.description}")
            if len(self.stale_leads) > 3:
                lines.append(f"    ... and {len(self.stale_leads) - 3} more")

        if self.data_concerns:
            lines.append(f"  Data quality ({len(self.data_concerns)}):")
            for f in self.data_concerns[:2]:
                lines.append(f"    {f.prospect_name}: {f.description}")

        return "\n".join(lines)


def interrogate_cards(db: Database) -> InterrogationReport:
    """Run proactive card interrogation.

    Reviews all active cards and identifies issues that Anne
    should surface in the morning brief or when presenting a card.

    Args:
        db: Database instance

    Returns:
        InterrogationReport with all findings
    """
    conn = db._get_connection()
    today = date.today()
    report = InterrogationReport()

    # 1. Find orphaned engaged (no follow-up date)
    orphan_rows = conn.execute(
        """SELECT p.id, p.first_name, p.last_name, p.engagement_stage,
                  p.prospect_score, c.name as company_name
           FROM prospects p
           LEFT JOIN companies c ON p.company_id = c.id
           WHERE p.population = ?
             AND (p.follow_up_date IS NULL OR p.follow_up_date = '')
           ORDER BY p.prospect_score DESC""",
        (Population.ENGAGED.value,),
    ).fetchall()

    for row in orphan_rows:
        name = f"{row['first_name']} {row['last_name']}".strip()
        stage = row["engagement_stage"] or "unknown"
        report.orphans.append(
            CardFinding(
                prospect_id=row["id"],
                prospect_name=name,
                company_name=row["company_name"] or "Unknown",
                finding_type="orphan",
                description=f"Engaged ({stage}) with NO follow-up date",
                severity="high",
                suggested_action="Set a follow-up date immediately — this card will fall through the cracks.",
            )
        )

    # 2. Find stale engaged (no activity in 14+ days)
    stale_cutoff = (today - timedelta(days=14)).isoformat()
    stale_rows = conn.execute(
        """SELECT p.id, p.first_name, p.last_name, p.engagement_stage,
                  c.name as company_name,
                  MAX(a.created_at) as last_activity
           FROM prospects p
           LEFT JOIN companies c ON p.company_id = c.id
           LEFT JOIN activities a ON a.prospect_id = p.id
           WHERE p.population = ?
             AND p.follow_up_date IS NOT NULL
           GROUP BY p.id
           HAVING last_activity IS NULL OR DATE(last_activity) < DATE(?)""",
        (Population.ENGAGED.value, stale_cutoff),
    ).fetchall()

    for row in stale_rows:
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
        report.stale_leads.append(
            CardFinding(
                prospect_id=row["id"],
                prospect_name=name,
                company_name=row["company_name"] or "Unknown",
                finding_type="stale_engaged",
                description=f"No activity for {days_stale} days ({stage})",
                severity="high" if days_stale >= 21 else "medium",
                suggested_action=f"Re-engage — {days_stale} days of silence risks losing momentum.",
            )
        )

    # 3. Find overdue follow-ups
    today_iso = today.isoformat()
    overdue_rows = conn.execute(
        """SELECT p.id, p.first_name, p.last_name, p.follow_up_date,
                  p.engagement_stage, c.name as company_name
           FROM prospects p
           LEFT JOIN companies c ON p.company_id = c.id
           WHERE p.follow_up_date IS NOT NULL
             AND DATE(p.follow_up_date) < DATE(?)
             AND p.population NOT IN (?, ?, ?)
           ORDER BY p.follow_up_date ASC""",
        (
            today_iso,
            Population.DEAD_DNC.value,
            Population.CLOSED_WON.value,
            Population.LOST.value,
        ),
    ).fetchall()

    for row in overdue_rows:
        try:
            fu_str = str(row["follow_up_date"])[:10]
            fu_date = date.fromisoformat(fu_str)
            days_overdue = (today - fu_date).days
        except (ValueError, TypeError):
            days_overdue = 0

        name = f"{row['first_name']} {row['last_name']}".strip()
        report.overdue_followups.append(
            CardFinding(
                prospect_id=row["id"],
                prospect_name=name,
                company_name=row["company_name"] or "Unknown",
                finding_type="overdue_followup",
                description=f"Follow-up due {fu_str} ({days_overdue} days ago)",
                severity="high" if days_overdue >= 7 else "medium",
                suggested_action=f"Call or email today — {days_overdue} days overdue.",
            )
        )

    # 4. Find high-score/low-confidence
    dq_rows = conn.execute(
        """SELECT p.id, p.first_name, p.last_name, p.prospect_score,
                  p.data_confidence, c.name as company_name
           FROM prospects p
           LEFT JOIN companies c ON p.company_id = c.id
           WHERE p.prospect_score >= 70
             AND p.data_confidence <= 40
             AND p.population NOT IN (?, ?, ?)
           ORDER BY p.prospect_score DESC
           LIMIT 10""",
        (
            Population.DEAD_DNC.value,
            Population.CLOSED_WON.value,
            Population.LOST.value,
        ),
    ).fetchall()

    for row in dq_rows:
        name = f"{row['first_name']} {row['last_name']}".strip()
        report.data_concerns.append(
            CardFinding(
                prospect_id=row["id"],
                prospect_name=name,
                company_name=row["company_name"] or "Unknown",
                finding_type="data_quality",
                description=(
                    f"Score {row['prospect_score']} but confidence only "
                    f"{row['data_confidence']} — data may be wrong"
                ),
                severity="medium",
                suggested_action="Verify contact info before next outreach.",
            )
        )

    logger.info(
        "Proactive interrogation complete",
        extra={
            "context": {
                "total": report.total_findings,
                "orphans": len(report.orphans),
                "stale": len(report.stale_leads),
                "overdue": len(report.overdue_followups),
                "data_quality": len(report.data_concerns),
            }
        },
    )

    return report


def get_card_findings(db: Database, prospect_id: int) -> list[CardFinding]:
    """Get findings for a specific card (used when presenting a card).

    Returns any relevant findings for this prospect that Anne
    should mention when presenting the card.
    """
    conn = db._get_connection()
    today = date.today()
    findings = []

    prospect = db.get_prospect(prospect_id)
    if not prospect:
        return findings

    company = db.get_company(prospect.company_id)
    company_name = company.name if company else "Unknown"
    name = prospect.full_name

    # Check orphan status
    if prospect.population == Population.ENGAGED and not prospect.follow_up_date:
        findings.append(
            CardFinding(
                prospect_id=prospect_id,
                prospect_name=name,
                company_name=company_name,
                finding_type="orphan",
                description="Engaged with no follow-up date",
                severity="high",
                suggested_action="Set a follow-up date before moving on.",
            )
        )

    # Check overdue
    if prospect.follow_up_date:
        try:
            fu_str = str(prospect.follow_up_date)[:10]
            fu_date = date.fromisoformat(fu_str)
            if fu_date < today:
                days = (today - fu_date).days
                findings.append(
                    CardFinding(
                        prospect_id=prospect_id,
                        prospect_name=name,
                        company_name=company_name,
                        finding_type="overdue_followup",
                        description=f"Follow-up is {days} days overdue",
                        severity="high" if days >= 7 else "medium",
                        suggested_action="This should be your top priority today.",
                    )
                )
        except (ValueError, TypeError):
            pass

    # Check stale
    if prospect.population == Population.ENGAGED:
        last_act = conn.execute(
            "SELECT MAX(created_at) as last_act FROM activities WHERE prospect_id = ?",
            (prospect_id,),
        ).fetchone()
        if last_act and last_act["last_act"]:
            try:
                act_str = str(last_act["last_act"])[:10]
                act_date = date.fromisoformat(act_str)
                days_stale = (today - act_date).days
                if days_stale >= 14:
                    findings.append(
                        CardFinding(
                            prospect_id=prospect_id,
                            prospect_name=name,
                            company_name=company_name,
                            finding_type="stale_engaged",
                            description=f"No activity for {days_stale} days",
                            severity="high" if days_stale >= 21 else "medium",
                            suggested_action="Momentum is fading. Re-engage now.",
                        )
                    )
            except (ValueError, TypeError):
                pass

    # Check data quality
    if prospect.prospect_score >= 70 and prospect.data_confidence <= 40:
        findings.append(
            CardFinding(
                prospect_id=prospect_id,
                prospect_name=name,
                company_name=company_name,
                finding_type="data_quality",
                description=(
                    f"Score {prospect.prospect_score} but confidence "
                    f"{prospect.data_confidence} — verify before calling"
                ),
                severity="medium",
                suggested_action="Verify contact info before outreach.",
            )
        )

    return findings

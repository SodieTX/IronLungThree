"""Learning engine - Qualitative patterns from notes.

Reads notes on won and lost deals to identify patterns:
    - "Lost to LoanPro because of price"
    - "Closed because they loved the borrower portal"
    - "Three losses mentioned pricing"

This is note-driven intelligence, not statistical modeling.
Works from day one with even a handful of closed deals.

Usage:
    from src.engine.learning import LearningEngine

    engine = LearningEngine(db)
    insights = engine.analyze_outcomes()
    suggestions = engine.get_suggestions_for_prospect(prospect_id)
"""

import re
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Population

logger = get_logger(__name__)

# Common competitor names in the lending technology space
KNOWN_COMPETITORS = [
    "loanpro",
    "loan pro",
    "encompass",
    "calyx",
    "bytepro",
    "byte pro",
    "mortgageflex",
    "mortgage flex",
    "fiserv",
    "sagent",
    "black knight",
    "ice mortgage",
    "finastra",
    "temenos",
    "nortridge",
    "turnkey lender",
    "mambu",
]

# Keyword categories for pattern extraction
WIN_KEYWORDS = {
    "borrower portal": "Borrower portal was a differentiator",
    "portal": "Portal features mentioned positively",
    "automation": "Automation capabilities valued",
    "integration": "Integration capabilities valued",
    "api": "API capabilities valued",
    "support": "Customer support was valued",
    "onboarding": "Onboarding experience was smooth",
    "pricing": "Pricing was competitive",
    "price": "Pricing was competitive",
    "demo": "Demo experience sealed the deal",
    "speed": "Speed of implementation valued",
    "flexibility": "Flexibility of platform valued",
    "compliance": "Compliance features valued",
    "reporting": "Reporting capabilities valued",
    "user friendly": "User-friendliness appreciated",
    "easy to use": "Ease of use appreciated",
    "referral": "Came through referral",
    "relationship": "Relationship was a factor",
}

LOSS_KEYWORDS = {
    "price": "Pricing was a concern",
    "pricing": "Pricing was a concern",
    "cost": "Cost was a factor",
    "expensive": "Perceived as too expensive",
    "budget": "Budget constraints",
    "feature": "Missing features",
    "timing": "Timing wasn't right",
    "not ready": "Not ready to switch",
    "contract": "Existing contract prevented switch",
    "competitor": "Went with a competitor",
    "integration": "Integration concerns",
    "security": "Security concerns",
    "migration": "Data migration concerns",
    "change management": "Change management concerns",
    "stakeholder": "Stakeholder alignment issues",
    "decision maker": "Couldn't reach decision maker",
    "no response": "Prospect went dark",
    "ghosted": "Prospect stopped responding",
}


@dataclass
class WinPattern:
    """Pattern from won deals.

    Attributes:
        pattern: Description of pattern
        count: How many deals showed this
        examples: Example deal notes
    """

    pattern: str
    count: int
    examples: list[str]


@dataclass
class LossPattern:
    """Pattern from lost deals.

    Attributes:
        pattern: Description of pattern
        count: How many deals showed this
        competitor: Competitor if mentioned
        examples: Example deal notes
    """

    pattern: str
    count: int
    competitor: Optional[str] = None
    examples: Optional[list[str]] = None


@dataclass
class LearningInsights:
    """Insights from outcome analysis.

    Attributes:
        win_patterns: Patterns from won deals
        loss_patterns: Patterns from lost deals
        top_competitors: Most common competitors
        win_rate: Overall win rate
        avg_cycle_days: Average days to close
    """

    win_patterns: list[WinPattern]
    loss_patterns: list[LossPattern]
    top_competitors: list[tuple[str, int]]  # (name, count)
    win_rate: Optional[float] = None
    avg_cycle_days: Optional[float] = None


class LearningEngine:
    """Note-based qualitative learning.

    Analyzes notes on closed and lost deals to find patterns.
    """

    def __init__(self, db: Database):
        """Initialize learning engine.

        Args:
            db: Database instance
        """
        self.db = db

    def analyze_outcomes(self) -> LearningInsights:
        """Analyze all won and lost deals for patterns.

        Returns:
            LearningInsights with patterns found
        """
        conn = self.db._get_connection()

        # Gather notes from won deals
        won_rows = conn.execute(
            """SELECT p.id, p.close_notes, p.notes, p.created_at, p.close_date,
                      c.name as company_name
               FROM prospects p
               LEFT JOIN companies c ON p.company_id = c.id
               WHERE p.population = ?""",
            (Population.CLOSED_WON.value,),
        ).fetchall()

        # Gather notes from lost deals
        lost_rows = conn.execute(
            """SELECT p.id, p.lost_reason, p.lost_competitor, p.notes,
                      c.name as company_name
               FROM prospects p
               LEFT JOIN companies c ON p.company_id = c.id
               WHERE p.population = ?""",
            (Population.LOST.value,),
        ).fetchall()

        # Also gather activity notes for richer context
        won_ids = [row["id"] for row in won_rows]
        lost_ids = [row["id"] for row in lost_rows]

        won_activity_notes = self._get_activity_notes(conn, won_ids)
        lost_activity_notes = self._get_activity_notes(conn, lost_ids)

        # Build combined note strings per deal
        won_notes = []
        for row in won_rows:
            parts = []
            if row["close_notes"]:
                parts.append(row["close_notes"])
            if row["notes"]:
                parts.append(row["notes"])
            parts.extend(won_activity_notes.get(row["id"], []))
            if parts:
                won_notes.append(" | ".join(parts))

        lost_notes = []
        for row in lost_rows:
            parts = []
            if row["lost_competitor"]:
                parts.append(f"Lost to {row['lost_competitor']}")
            if row["lost_reason"]:
                parts.append(f"Reason: {row['lost_reason']}")
            if row["notes"]:
                parts.append(row["notes"])
            parts.extend(lost_activity_notes.get(row["id"], []))
            if parts:
                lost_notes.append(" | ".join(parts))

        # Extract patterns
        win_patterns = self._extract_win_patterns(won_notes)
        loss_patterns = self._extract_loss_patterns(lost_notes)

        # Find competitors across all lost deal notes
        all_loss_text = lost_notes[:]
        for row in lost_rows:
            if row["lost_competitor"]:
                all_loss_text.append(row["lost_competitor"])
        competitor_counts = self._find_competitor_mentions(all_loss_text)
        top_competitors = competitor_counts.most_common(5)

        # Calculate win rate
        total_outcomes = len(won_rows) + len(lost_rows)
        win_rate = len(won_rows) / total_outcomes if total_outcomes > 0 else None

        # Calculate average cycle days from won deals
        cycle_days = []
        for row in won_rows:
            if row["created_at"] and row["close_date"]:
                try:
                    from datetime import date as date_type

                    created = str(row["created_at"])[:10]
                    closed = str(row["close_date"])[:10]
                    created_date = date_type.fromisoformat(created)
                    closed_date = date_type.fromisoformat(closed)
                    days = (closed_date - created_date).days
                    if days >= 0:
                        cycle_days.append(days)
                except (ValueError, TypeError):
                    pass

        avg_cycle = sum(cycle_days) / len(cycle_days) if cycle_days else None

        insights = LearningInsights(
            win_patterns=win_patterns,
            loss_patterns=loss_patterns,
            top_competitors=top_competitors,
            win_rate=win_rate,
            avg_cycle_days=avg_cycle,
        )

        logger.info(
            "Learning analysis complete",
            extra={
                "context": {
                    "won_deals": len(won_rows),
                    "lost_deals": len(lost_rows),
                    "win_patterns": len(win_patterns),
                    "loss_patterns": len(loss_patterns),
                    "win_rate": win_rate,
                    "avg_cycle_days": avg_cycle,
                }
            },
        )

        return insights

    def get_suggestions_for_prospect(self, prospect_id: int) -> list[str]:
        """Get suggestions based on similar past deals.

        Args:
            prospect_id: Prospect to get suggestions for

        Returns:
            List of suggestions based on patterns
        """
        insights = self.analyze_outcomes()
        prospect = self.db.get_prospect(prospect_id)
        if not prospect:
            return []

        suggestions = []

        # If we have win patterns, suggest leveraging them
        if insights.win_patterns:
            top_win = insights.win_patterns[0]
            suggestions.append(
                f"Your top win driver is: {top_win.pattern} "
                f"(seen in {top_win.count} deals). Lead with this."
            )

        # If we have loss patterns, suggest addressing them proactively
        if insights.loss_patterns:
            top_loss = insights.loss_patterns[0]
            suggestions.append(
                f"Watch out: {top_loss.pattern} has caused "
                f"{top_loss.count} losses. Address this early."
            )

        # Competitor intelligence
        if insights.top_competitors:
            comp_name, comp_count = insights.top_competitors[0]
            suggestions.append(
                f"Top competitor is {comp_name} ({comp_count} deals lost). "
                f"Know your differentiators."
            )

        # Win rate context
        if insights.win_rate is not None:
            pct = round(insights.win_rate * 100)
            suggestions.append(f"Current win rate: {pct}%.")

        # Cycle time context
        if insights.avg_cycle_days is not None:
            suggestions.append(
                f"Average deal cycle: {round(insights.avg_cycle_days)} days. "
                f"Use this to set expectations."
            )

        # Check prospect-specific intel
        nuggets = self.db.get_intel_nuggets(prospect_id)
        competitor_nuggets = [n for n in nuggets if n.category.value == "competitor"]
        if competitor_nuggets:
            comp_content = competitor_nuggets[0].content
            suggestions.append(
                f"Intel shows competitor involvement: {comp_content}. " f"Prepare differentiators."
            )

        return suggestions

    def _get_activity_notes(self, conn, prospect_ids: list[int]) -> dict[int, list[str]]:
        """Get activity notes grouped by prospect ID."""
        if not prospect_ids:
            return {}

        placeholders = ",".join("?" for _ in prospect_ids)
        rows = conn.execute(
            f"""SELECT prospect_id, notes
                FROM activities
                WHERE prospect_id IN ({placeholders})
                  AND notes IS NOT NULL AND notes != ''
                ORDER BY created_at DESC""",
            prospect_ids,
        ).fetchall()

        result: dict[int, list[str]] = {}
        for row in rows:
            pid = row["prospect_id"]
            if pid not in result:
                result[pid] = []
            result[pid].append(row["notes"])

        return result

    def _extract_win_patterns(self, notes: list[str]) -> list[WinPattern]:
        """Extract patterns from winning deal notes."""
        if not notes:
            return []

        pattern_counts: Counter = Counter()
        pattern_examples: dict[str, list[str]] = {}

        for note in notes:
            note_lower = note.lower()
            matched_in_note: set[str] = set()
            for keyword, pattern_desc in WIN_KEYWORDS.items():
                if keyword in note_lower and pattern_desc not in matched_in_note:
                    pattern_counts[pattern_desc] += 1
                    matched_in_note.add(pattern_desc)
                    if pattern_desc not in pattern_examples:
                        pattern_examples[pattern_desc] = []
                    # Keep first 3 examples, truncated
                    if len(pattern_examples[pattern_desc]) < 3:
                        truncated = note[:120] + "..." if len(note) > 120 else note
                        pattern_examples[pattern_desc].append(truncated)

        # Sort by frequency, return patterns with 1+ occurrence
        patterns = []
        for desc, count in pattern_counts.most_common():
            patterns.append(
                WinPattern(
                    pattern=desc,
                    count=count,
                    examples=pattern_examples.get(desc, []),
                )
            )

        return patterns

    def _extract_loss_patterns(self, notes: list[str]) -> list[LossPattern]:
        """Extract patterns from lost deal notes."""
        if not notes:
            return []

        pattern_counts: Counter = Counter()
        pattern_examples: dict[str, list[str]] = {}
        pattern_competitors: dict[str, Counter] = {}

        for note in notes:
            note_lower = note.lower()
            matched_in_note: set[str] = set()
            for keyword, pattern_desc in LOSS_KEYWORDS.items():
                if keyword in note_lower and pattern_desc not in matched_in_note:
                    pattern_counts[pattern_desc] += 1
                    matched_in_note.add(pattern_desc)
                    if pattern_desc not in pattern_examples:
                        pattern_examples[pattern_desc] = []
                    if len(pattern_examples[pattern_desc]) < 3:
                        truncated = note[:120] + "..." if len(note) > 120 else note
                        pattern_examples[pattern_desc].append(truncated)

                    # Check for competitor mentions in this note
                    if pattern_desc not in pattern_competitors:
                        pattern_competitors[pattern_desc] = Counter()
                    for comp in KNOWN_COMPETITORS:
                        if comp in note_lower:
                            pattern_competitors[pattern_desc][comp] += 1

        patterns = []
        for desc, count in pattern_counts.most_common():
            # Find the most mentioned competitor for this pattern
            comp_counter = pattern_competitors.get(desc, Counter())
            top_comp = comp_counter.most_common(1)[0][0] if comp_counter else None

            patterns.append(
                LossPattern(
                    pattern=desc,
                    count=count,
                    competitor=top_comp,
                    examples=pattern_examples.get(desc, []),
                )
            )

        return patterns

    def _find_competitor_mentions(self, notes: list[str]) -> Counter:
        """Find competitor mentions in notes."""
        mentions: Counter = Counter()

        for note in notes:
            note_lower = note.lower()
            counted_in_note: set[str] = set()
            for comp in KNOWN_COMPETITORS:
                if comp in note_lower and comp not in counted_in_note:
                    # Normalize multi-word variants to canonical name
                    canonical = comp.replace(" ", "")
                    mentions[canonical] += 1
                    counted_in_note.add(comp)

        return mentions

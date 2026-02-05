"""Troubled cards service — identifies problem prospects.

Troubled cards are prospects that need attention because:
- Follow-up is overdue (> 2 days past due)
- Stalled: no activity in 14+ days despite being engaged
- Conflicting data: suspect contact methods flagged
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Population

logger = get_logger(__name__)


@dataclass
class TroubledCard:
    prospect_id: int
    prospect_name: str
    company_name: str
    population: str
    trouble_type: str  # "overdue", "stalled", "suspect_data"
    detail: str
    days_overdue: int = 0


class TroubledCardsService:
    """Identifies prospects that need attention.

    Three categories:
    1. Overdue: follow-up date > 2 days in the past
    2. Stalled: engaged prospect with no activity in 14+ days
    3. Suspect data: contact methods flagged as potentially wrong
    """

    OVERDUE_THRESHOLD_DAYS = 2
    STALLED_THRESHOLD_DAYS = 14

    def __init__(self, db: Database):
        self._db = db

    def get_troubled_cards(self, target_date: Optional[date] = None) -> list[TroubledCard]:
        """Get all troubled cards, sorted by severity.

        Args:
            target_date: Date to evaluate against (defaults to today)

        Returns:
            List of TroubledCard, most severe first
        """
        if target_date is None:
            target_date = date.today()

        cards: list[TroubledCard] = []
        cards.extend(self._find_overdue(target_date))
        cards.extend(self._find_stalled(target_date))
        cards.extend(self._find_suspect_data())

        # Deduplicate by prospect_id (keep highest severity)
        seen: dict[int, TroubledCard] = {}
        for card in cards:
            if card.prospect_id not in seen:
                seen[card.prospect_id] = card
            else:
                # Keep the one with more days overdue or the more severe type
                existing = seen[card.prospect_id]
                if card.days_overdue > existing.days_overdue:
                    seen[card.prospect_id] = card

        result = list(seen.values())
        result.sort(key=lambda c: c.days_overdue, reverse=True)
        return result

    def _find_overdue(self, target_date: date) -> list[TroubledCard]:
        """Find prospects with overdue follow-ups."""
        conn = self._db._get_connection()
        cutoff = target_date - timedelta(days=self.OVERDUE_THRESHOLD_DAYS)

        rows = conn.execute(
            """SELECT p.id, p.first_name, p.last_name, p.population,
                      p.follow_up_date, c.name as company_name
               FROM prospects p
               LEFT JOIN companies c ON p.company_id = c.id
               WHERE p.population IN (?, ?)
                 AND p.follow_up_date IS NOT NULL
                 AND DATE(p.follow_up_date) < ?
               ORDER BY p.follow_up_date ASC""",
            (
                Population.ENGAGED.value,
                Population.UNENGAGED.value,
                cutoff.isoformat(),
            ),
        ).fetchall()

        cards: list[TroubledCard] = []
        for row in rows:
            follow_date = datetime.fromisoformat(row["follow_up_date"]).date()
            days = (target_date - follow_date).days
            cards.append(
                TroubledCard(
                    prospect_id=row["id"],
                    prospect_name=f"{row['first_name']} {row['last_name']}".strip(),
                    company_name=row["company_name"] or "Unknown",
                    population=row["population"],
                    trouble_type="overdue",
                    detail=f"Follow-up {days} days overdue",
                    days_overdue=days,
                )
            )
        return cards

    def _find_stalled(self, target_date: date) -> list[TroubledCard]:
        """Find engaged prospects with no recent activity."""
        conn = self._db._get_connection()
        cutoff = (target_date - timedelta(days=self.STALLED_THRESHOLD_DAYS)).isoformat()

        rows = conn.execute(
            """SELECT p.id, p.first_name, p.last_name, p.population,
                      c.name as company_name,
                      MAX(a.created_at) as last_activity
               FROM prospects p
               LEFT JOIN companies c ON p.company_id = c.id
               LEFT JOIN activities a ON p.id = a.prospect_id
               WHERE p.population = ?
               GROUP BY p.id
               HAVING last_activity IS NULL OR DATE(last_activity) < ?""",
            (Population.ENGAGED.value, cutoff),
        ).fetchall()

        cards: list[TroubledCard] = []
        for row in rows:
            last = row["last_activity"]
            if last:
                last_date = datetime.fromisoformat(last).date()
                days = (target_date - last_date).days
            else:
                days = self.STALLED_THRESHOLD_DAYS
            cards.append(
                TroubledCard(
                    prospect_id=row["id"],
                    prospect_name=f"{row['first_name']} {row['last_name']}".strip(),
                    company_name=row["company_name"] or "Unknown",
                    population=row["population"],
                    trouble_type="stalled",
                    detail=f"No activity in {days} days",
                    days_overdue=days,
                )
            )
        return cards

    def _find_suspect_data(self) -> list[TroubledCard]:
        """Find prospects with suspect contact methods."""
        conn = self._db._get_connection()

        rows = conn.execute(
            """SELECT p.id, p.first_name, p.last_name, p.population,
                      c.name as company_name,
                      cm.type as method_type, cm.value as method_value
               FROM contact_methods cm
               JOIN prospects p ON cm.prospect_id = p.id
               LEFT JOIN companies c ON p.company_id = c.id
               WHERE cm.is_suspect = 1""",
        ).fetchall()

        cards: list[TroubledCard] = []
        for row in rows:
            cards.append(
                TroubledCard(
                    prospect_id=row["id"],
                    prospect_name=f"{row['first_name']} {row['last_name']}".strip(),
                    company_name=row["company_name"] or "Unknown",
                    population=row["population"],
                    trouble_type="suspect_data",
                    detail=f"Suspect {row['method_type']}: {row['method_value']}",
                    days_overdue=0,
                )
            )
        return cards

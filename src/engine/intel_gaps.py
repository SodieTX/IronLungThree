"""Intel gaps service — identifies missing non-critical information.

Intel gaps are prospects where useful (but not critical) data is missing:
- No company domain
- No loan types recorded
- No intel nuggets extracted
- No company size
- Missing title
"""

from dataclasses import dataclass
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Population

logger = get_logger(__name__)


@dataclass
class IntelGap:
    prospect_id: int
    prospect_name: str
    company_name: str
    gap_type: str
    detail: str


class IntelGapsService:
    """Identifies prospects with missing non-critical data.

    These are not "broken" prospects (which are missing phone/email).
    Intel gaps are useful-to-have data that would make calls and
    emails more effective.
    """

    def __init__(self, db: Database):
        self._db = db

    def get_intel_gaps(
        self,
        populations: Optional[list[Population]] = None,
    ) -> list[IntelGap]:
        """Get all intel gaps for active prospects.

        Args:
            populations: Filter to these populations (default: engaged + unengaged)

        Returns:
            List of IntelGap records
        """
        if populations is None:
            populations = [Population.ENGAGED, Population.UNENGAGED]

        pop_values = [p.value for p in populations]

        gaps: list[IntelGap] = []
        gaps.extend(self._find_missing_domains(pop_values))
        gaps.extend(self._find_missing_titles(pop_values))
        gaps.extend(self._find_missing_company_size(pop_values))
        gaps.extend(self._find_missing_intel_nuggets(pop_values))

        return gaps

    def get_gap_summary(self, populations: Optional[list[Population]] = None) -> dict[str, int]:
        """Get count of gaps by type.

        Returns:
            Dict mapping gap_type to count
        """
        gaps = self.get_intel_gaps(populations)
        summary: dict[str, int] = {}
        for gap in gaps:
            summary[gap.gap_type] = summary.get(gap.gap_type, 0) + 1
        return summary

    def _find_missing_domains(self, pop_values: list[str]) -> list[IntelGap]:
        """Find companies without a domain."""
        conn = self._db._get_connection()
        placeholders = ",".join("?" * len(pop_values))

        rows = conn.execute(
            f"""SELECT DISTINCT p.id, p.first_name, p.last_name,
                       c.name as company_name
                FROM prospects p
                JOIN companies c ON p.company_id = c.id
                WHERE p.population IN ({placeholders})
                  AND (c.domain IS NULL OR c.domain = '')""",
            pop_values,
        ).fetchall()

        return [
            IntelGap(
                prospect_id=row["id"],
                prospect_name=f"{row['first_name']} {row['last_name']}".strip(),
                company_name=row["company_name"] or "Unknown",
                gap_type="missing_domain",
                detail="No company website/domain",
            )
            for row in rows
        ]

    def _find_missing_titles(self, pop_values: list[str]) -> list[IntelGap]:
        """Find prospects without a job title."""
        conn = self._db._get_connection()
        placeholders = ",".join("?" * len(pop_values))

        rows = conn.execute(
            f"""SELECT p.id, p.first_name, p.last_name,
                       c.name as company_name
                FROM prospects p
                LEFT JOIN companies c ON p.company_id = c.id
                WHERE p.population IN ({placeholders})
                  AND (p.title IS NULL OR p.title = '')""",
            pop_values,
        ).fetchall()

        return [
            IntelGap(
                prospect_id=row["id"],
                prospect_name=f"{row['first_name']} {row['last_name']}".strip(),
                company_name=row["company_name"] or "Unknown",
                gap_type="missing_title",
                detail="No job title",
            )
            for row in rows
        ]

    def _find_missing_company_size(self, pop_values: list[str]) -> list[IntelGap]:
        """Find companies without size info."""
        conn = self._db._get_connection()
        placeholders = ",".join("?" * len(pop_values))

        rows = conn.execute(
            f"""SELECT DISTINCT p.id, p.first_name, p.last_name,
                       c.name as company_name
                FROM prospects p
                JOIN companies c ON p.company_id = c.id
                WHERE p.population IN ({placeholders})
                  AND (c.size IS NULL OR c.size = '')""",
            pop_values,
        ).fetchall()

        return [
            IntelGap(
                prospect_id=row["id"],
                prospect_name=f"{row['first_name']} {row['last_name']}".strip(),
                company_name=row["company_name"] or "Unknown",
                gap_type="missing_company_size",
                detail="No company size recorded",
            )
            for row in rows
        ]

    def _find_missing_intel_nuggets(self, pop_values: list[str]) -> list[IntelGap]:
        """Find engaged prospects with no intel nuggets."""
        conn = self._db._get_connection()
        # Only check engaged — unengaged may not have had a conversation yet
        if Population.ENGAGED.value not in pop_values:
            return []

        rows = conn.execute(
            """SELECT p.id, p.first_name, p.last_name,
                      c.name as company_name
               FROM prospects p
               LEFT JOIN companies c ON p.company_id = c.id
               LEFT JOIN intel_nuggets n ON p.id = n.prospect_id
               WHERE p.population = ?
                 AND n.id IS NULL""",
            (Population.ENGAGED.value,),
        ).fetchall()

        return [
            IntelGap(
                prospect_id=row["id"],
                prospect_name=f"{row['first_name']} {row['last_name']}".strip(),
                company_name=row["company_name"] or "Unknown",
                gap_type="missing_intel",
                detail="No intel nuggets extracted",
            )
            for row in rows
        ]

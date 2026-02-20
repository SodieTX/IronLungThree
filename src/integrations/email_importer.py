"""Email CSV importer for prospect card enrichment.

Imports Outlook email exports to enrich prospect cards with email history.
Available before Phase 3 Graph API integration.

Usage:
    from src.integrations.email_importer import EmailCSVImporter

    importer = EmailCSVImporter(db)
    result = importer.import_emails(Path("sent_emails.csv"))
"""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.exceptions import ImportError_
from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Activity, ActivityType, AttemptType

logger = get_logger(__name__)


@dataclass
class EmailImportResult:
    """Result of email CSV import.

    Attributes:
        total_emails: Total emails in file
        matched_emails: Emails matched to prospects
        unmatched_emails: Emails not matched
        activities_created: Activity records created
    """

    total_emails: int = 0
    matched_emails: int = 0
    unmatched_emails: int = 0
    activities_created: int = 0


class EmailCSVImporter:
    """Import email history from Outlook CSV exports.

    Matches emails to prospects by email address and creates
    activity records with subject, body, and date.

    This is a Phase 2 feature that provides email enrichment
    before the Graph API integration is built in Phase 3.
    """

    def __init__(self, db: Database):
        """Initialize email importer.

        Args:
            db: Database instance
        """
        self.db = db

    def import_emails(
        self,
        path: Path,
        direction: str = "sent",
    ) -> EmailImportResult:
        """Import emails from CSV.

        Parses the CSV, matches each email to a prospect, and creates
        activity records for matched emails. Deduplicates by checking
        for existing activities with the same subject and date.

        Args:
            path: Path to email CSV
            direction: "sent" or "received"

        Returns:
            Import result with counts

        Raises:
            ImportError_: If the file cannot be read or parsed
        """
        rows = self._parse_outlook_csv(path)
        result = EmailImportResult(total_emails=len(rows))

        activity_type = (
            ActivityType.EMAIL_SENT if direction == "sent" else ActivityType.EMAIL_RECEIVED
        )

        for row in rows:
            email_addr = row.get("to", "") if direction == "sent" else row.get("from", "")
            if not email_addr:
                result.unmatched_emails += 1
                continue

            prospect_id = self._match_to_prospect(email_addr.strip())
            if prospect_id is None:
                result.unmatched_emails += 1
                continue

            result.matched_emails += 1

            # Build dedup marker from subject + date
            subject = row.get("subject", "")
            date_str = row.get("date", "")
            marker = f"csv_import:{subject}:{date_str}"

            # Check for duplicate
            conn = self.db._get_connection()
            existing = conn.execute(
                "SELECT id FROM activities WHERE prospect_id = ? "
                "AND activity_type = ? AND notes LIKE ? LIMIT 1",
                (prospect_id, activity_type.value, f"%{marker}%"),
            ).fetchone()

            if existing:
                continue

            activity = Activity(
                prospect_id=prospect_id,
                activity_type=activity_type,
                email_subject=subject,
                email_body=(row.get("body", "") or "")[:500],
                attempt_type=AttemptType.PERSONAL,
                notes=marker,
                created_by="csv_import",
            )

            try:
                self.db.create_activity(activity)
                result.activities_created += 1
            except Exception as exc:
                logger.warning(
                    "Failed to create email activity from CSV",
                    extra={"context": {"email": email_addr, "error": str(exc)}},
                )

        logger.info(
            "Email CSV import complete",
            extra={
                "context": {
                    "total": result.total_emails,
                    "matched": result.matched_emails,
                    "created": result.activities_created,
                }
            },
        )
        return result

    def _parse_outlook_csv(
        self,
        path: Path,
    ) -> list[dict]:
        """Parse Outlook email export CSV.

        Handles common Outlook export column names and normalizes them.
        Tries UTF-8 first, then falls back to latin-1 encoding.

        Expected columns vary by export type, but typically include:
            - From, To, Subject, Body, Received (for inbox)
            - To, Subject, Body, Sent (for sent items)

        Returns:
            List of dicts with normalized keys: from, to, subject, body, date
        """
        if not path.exists():
            raise ImportError_(f"File not found: {path}")

        # Try UTF-8 first, then latin-1
        content_lines = None
        for encoding in ("utf-8", "latin-1"):
            try:
                content_lines = path.read_text(encoding=encoding).splitlines()
                break
            except UnicodeDecodeError:
                continue

        if content_lines is None:
            raise ImportError_(f"Cannot decode file: {path}")

        if not content_lines:
            return []

        reader = csv.DictReader(content_lines)
        rows: list[dict] = []

        # Map common Outlook CSV column names to our normalized keys
        column_map = {
            "from": "from",
            "from: (address)": "from",
            "sender": "from",
            "sender address": "from",
            "to": "to",
            "to: (address)": "to",
            "recipient": "to",
            "recipient address": "to",
            "subject": "subject",
            "body": "body",
            "body preview": "body",
            "received": "date",
            "sent": "date",
            "date": "date",
            "date/time": "date",
            "sentdatetime": "date",
            "receiveddatetime": "date",
        }

        for csv_row in reader:
            normalized: dict[str, str] = {}
            for col_name, value in csv_row.items():
                if col_name is None:
                    continue
                mapped = column_map.get(col_name.strip().lower())
                if mapped and mapped not in normalized:
                    normalized[mapped] = (value or "").strip()
            if normalized:
                rows.append(normalized)

        return rows

    def _match_to_prospect(self, email_address: str) -> Optional[int]:
        """Find prospect ID by email address.

        Returns prospect_id or None if not found.
        """
        return self.db.find_prospect_by_email(email_address)

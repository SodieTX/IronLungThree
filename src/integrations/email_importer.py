"""Email CSV importer for prospect card enrichment.

Imports Outlook email exports to enrich prospect cards with email history.
Available before Phase 3 Graph API integration.

Usage:
    from src.integrations.email_importer import EmailCSVImporter

    importer = EmailCSVImporter(db)
    result = importer.import_emails(Path("sent_emails.csv"))
"""

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

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

        Args:
            path: Path to email CSV
            direction: "sent" or "received"

        Returns:
            Import result with counts
        """
        result = EmailImportResult()

        rows = self._parse_outlook_csv(path)
        result.total_emails = len(rows)

        activity_type = (
            ActivityType.EMAIL_SENT if direction == "sent" else ActivityType.EMAIL_RECEIVED
        )

        for row in rows:
            # Get the email address to match on
            if direction == "sent":
                email_addr = row.get("to", "")
            else:
                email_addr = row.get("from", "")

            if not email_addr:
                result.unmatched_emails += 1
                continue

            prospect_id = self._match_to_prospect(email_addr)
            if prospect_id is None:
                result.unmatched_emails += 1
                continue

            result.matched_emails += 1

            # Check for duplicate by subject + date
            subject = row.get("subject", "")
            date_str = row.get("date", "")
            marker = f"csv_import:{subject[:50]}|{date_str}"

            conn = self.db._get_connection()
            existing = conn.execute(
                "SELECT id FROM activities WHERE notes LIKE ? AND prospect_id = ? LIMIT 1",
                (f"%{marker}%", prospect_id),
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
            except Exception as e:
                logger.warning(f"Failed to create activity for {email_addr}: {e}")

        logger.info(
            f"Email import complete: {result.activities_created} activities from {result.total_emails} emails",
            extra={"context": {"path": str(path), "direction": direction}},
        )
        return result

    def _parse_outlook_csv(
        self,
        path: Path,
    ) -> list[dict]:
        """Parse Outlook email export CSV.

        Expected columns vary by export type, but typically include:
            - From, To, Subject, Body, Received (for inbox)
            - To, Subject, Body, Sent (for sent items)

        Handles common Outlook CSV column name variations.
        """
        if not path.exists():
            logger.error(f"CSV file not found: {path}")
            return []

        rows: list[dict] = []

        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    logger.error(f"No headers found in CSV: {path}")
                    return []

                # Normalize column names to lowercase
                for row in reader:
                    normalized: dict[str, str] = {}
                    for key, value in row.items():
                        if key is None:
                            continue
                        k = key.strip().lower()

                        # Map common Outlook column names
                        if k in ("from", "from: (address)", "sender"):
                            normalized["from"] = (value or "").strip()
                        elif k in ("to", "to: (address)", "recipients"):
                            normalized["to"] = (value or "").strip()
                        elif k in ("subject",):
                            normalized["subject"] = (value or "").strip()
                        elif k in ("body", "body preview", "notes"):
                            normalized["body"] = (value or "").strip()
                        elif k in ("received", "received date", "date/time", "sent", "sent date"):
                            normalized["date"] = (value or "").strip()

                    if normalized.get("from") or normalized.get("to"):
                        rows.append(normalized)

        except Exception as e:
            logger.error(f"Failed to parse CSV {path}: {e}")

        logger.info(f"Parsed {len(rows)} emails from {path}")
        return rows

    def _match_to_prospect(self, email_address: str) -> Optional[int]:
        """Find prospect ID by email address.

        Returns prospect_id or None if not found.
        """
        # Clean the email address
        email = email_address.strip().lower()

        # Handle "Name <email@example.com>" format
        match = re.search(r"<([^>]+)>", email)
        if match:
            email = match.group(1)

        if not email or "@" not in email:
            return None

        return self.db.find_prospect_by_email(email)

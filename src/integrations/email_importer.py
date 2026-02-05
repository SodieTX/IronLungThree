"""Email CSV importer for prospect card enrichment.

Imports Outlook email exports to enrich prospect cards with email history.
Available before Phase 3 Graph API integration.

Usage:
    from src.integrations.email_importer import EmailCSVImporter

    importer = EmailCSVImporter(db)
    result = importer.import_emails(Path("sent_emails.csv"))
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database

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
        raise NotImplementedError("Phase 2")

    def _parse_outlook_csv(
        self,
        path: Path,
    ) -> list[dict]:
        """Parse Outlook email export CSV.

        Expected columns vary by export type, but typically include:
            - From, To, Subject, Body, Received (for inbox)
            - To, Subject, Body, Sent (for sent items)
        """
        raise NotImplementedError("Phase 2")

    def _match_to_prospect(self, email_address: str) -> Optional[int]:
        """Find prospect ID by email address.

        Returns prospect_id or None if not found.
        """
        raise NotImplementedError("Phase 2")

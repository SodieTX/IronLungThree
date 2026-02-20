"""Tests for email CSV importer (src/integrations/email_importer.py).

Covers:
    - EmailCSVImporter.import_emails: CSV parsing, matching, activity creation
    - EmailCSVImporter._parse_outlook_csv: column mapping, encoding fallback
    - EmailCSVImporter._match_to_prospect: email-based prospect lookup
    - Deduplication: same email imported twice creates only one activity
    - Error handling: missing files, empty files, unmatched emails
"""

import textwrap
from pathlib import Path

import pytest

from src.db.database import Database
from src.db.models import (
    ActivityType,
    Company,
    ContactMethod,
    ContactMethodType,
    Prospect,
)
from src.integrations.email_importer import EmailCSVImporter, EmailImportResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_prospect_with_email(
    db: Database, email: str, first_name: str = "Test", last_name: str = "User"
) -> int:
    """Create company + prospect + email contact method. Return prospect_id."""
    company_id = db.create_company(Company(name=f"{first_name} Co"))
    pid = db.create_prospect(
        Prospect(company_id=company_id, first_name=first_name, last_name=last_name)
    )
    db.create_contact_method(
        ContactMethod(
            prospect_id=pid,
            type=ContactMethodType.EMAIL,
            value=email,
            is_primary=True,
        )
    )
    return pid


# ===========================================================================
# _parse_outlook_csv
# ===========================================================================


class TestParseOutlookCSV:
    """Parsing email CSV exports."""

    def test_parses_standard_sent_csv(self, tmp_path: Path, memory_db: Database):
        """Standard Outlook sent export with To/Subject/Body/Sent columns."""
        csv_file = tmp_path / "sent.csv"
        csv_file.write_text(
            "To,Subject,Body,Sent\n"
            "john@example.com,Hello,Hi John,2026-02-10\n"
            "jane@example.com,Follow Up,Checking in,2026-02-11\n",
            encoding="utf-8",
        )

        importer = EmailCSVImporter(memory_db)
        rows = importer._parse_outlook_csv(csv_file)

        assert len(rows) == 2
        assert rows[0]["to"] == "john@example.com"
        assert rows[0]["subject"] == "Hello"
        assert rows[0]["date"] == "2026-02-10"

    def test_parses_received_csv_with_from_column(self, tmp_path: Path, memory_db: Database):
        """Inbox export with From/Subject/Body/Received columns."""
        csv_file = tmp_path / "inbox.csv"
        csv_file.write_text(
            "From,Subject,Body,Received\n" "sender@test.com,Re: Proposal,Looks good,2026-02-12\n",
            encoding="utf-8",
        )

        importer = EmailCSVImporter(memory_db)
        rows = importer._parse_outlook_csv(csv_file)

        assert len(rows) == 1
        assert rows[0]["from"] == "sender@test.com"
        assert rows[0]["subject"] == "Re: Proposal"

    def test_handles_empty_csv(self, tmp_path: Path, memory_db: Database):
        """CSV with headers only returns empty list."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("To,Subject,Body,Sent\n", encoding="utf-8")

        importer = EmailCSVImporter(memory_db)
        rows = importer._parse_outlook_csv(csv_file)
        assert rows == []

    def test_raises_on_missing_file(self, tmp_path: Path, memory_db: Database):
        """Non-existent file raises ImportError_."""
        from src.core.exceptions import ImportError_

        importer = EmailCSVImporter(memory_db)
        with pytest.raises(ImportError_):
            importer._parse_outlook_csv(tmp_path / "nonexistent.csv")

    def test_falls_back_to_latin1_encoding(self, tmp_path: Path, memory_db: Database):
        """Files with non-UTF-8 encoding are handled via latin-1 fallback."""
        csv_file = tmp_path / "latin1.csv"
        content = "To,Subject,Body,Sent\njohn@example.com,Héllo,Café,2026-02-10\n"
        csv_file.write_bytes(content.encode("latin-1"))

        importer = EmailCSVImporter(memory_db)
        rows = importer._parse_outlook_csv(csv_file)
        assert len(rows) == 1
        assert rows[0]["to"] == "john@example.com"

    def test_maps_alternate_column_names(self, tmp_path: Path, memory_db: Database):
        """Alternate column names (Sender, Recipient, etc.) are mapped."""
        csv_file = tmp_path / "alternate.csv"
        csv_file.write_text(
            "Sender,Recipient,Subject,Body Preview,Date\n"
            "from@test.com,to@test.com,Test Subject,Body text,2026-02-10\n",
            encoding="utf-8",
        )

        importer = EmailCSVImporter(memory_db)
        rows = importer._parse_outlook_csv(csv_file)

        assert len(rows) == 1
        assert rows[0]["from"] == "from@test.com"
        assert rows[0]["to"] == "to@test.com"
        assert rows[0]["subject"] == "Test Subject"


# ===========================================================================
# _match_to_prospect
# ===========================================================================


class TestMatchToProspect:
    """Email-based prospect matching."""

    def test_finds_existing_prospect(self, memory_db: Database):
        """Known email returns prospect ID."""
        pid = _setup_prospect_with_email(memory_db, "known@example.com")
        importer = EmailCSVImporter(memory_db)
        assert importer._match_to_prospect("known@example.com") == pid

    def test_returns_none_for_unknown(self, memory_db: Database):
        """Unknown email returns None."""
        importer = EmailCSVImporter(memory_db)
        assert importer._match_to_prospect("nobody@example.com") is None

    def test_case_insensitive_match(self, memory_db: Database):
        """Email matching is case-insensitive."""
        pid = _setup_prospect_with_email(memory_db, "case@example.com")
        importer = EmailCSVImporter(memory_db)
        assert importer._match_to_prospect("CASE@EXAMPLE.COM") == pid


# ===========================================================================
# import_emails
# ===========================================================================


class TestImportEmails:
    """Full import pipeline: parse -> match -> create activities."""

    def test_import_sent_creates_activities(self, tmp_path: Path, memory_db: Database):
        """Sent emails matched to prospects create EMAIL_SENT activities."""
        pid = _setup_prospect_with_email(memory_db, "prospect@example.com", "Jeff", "Smith")

        csv_file = tmp_path / "sent.csv"
        csv_file.write_text(
            "To,Subject,Body,Sent\n" "prospect@example.com,Hello Jeff,Reaching out,2026-02-10\n",
            encoding="utf-8",
        )

        importer = EmailCSVImporter(memory_db)
        result = importer.import_emails(csv_file, direction="sent")

        assert result.total_emails == 1
        assert result.matched_emails == 1
        assert result.activities_created == 1
        assert result.unmatched_emails == 0

        activities = memory_db.get_activities(pid)
        sent = [a for a in activities if a.activity_type == ActivityType.EMAIL_SENT]
        assert len(sent) == 1
        assert "Hello Jeff" in (sent[0].email_subject or "")

    def test_import_received_creates_activities(self, tmp_path: Path, memory_db: Database):
        """Received emails create EMAIL_RECEIVED activities."""
        pid = _setup_prospect_with_email(memory_db, "sender@example.com", "Jane", "Doe")

        csv_file = tmp_path / "inbox.csv"
        csv_file.write_text(
            "From,Subject,Body,Received\n" "sender@example.com,Re: Demo,Sounds great,2026-02-12\n",
            encoding="utf-8",
        )

        importer = EmailCSVImporter(memory_db)
        result = importer.import_emails(csv_file, direction="received")

        assert result.total_emails == 1
        assert result.matched_emails == 1
        assert result.activities_created == 1

        activities = memory_db.get_activities(pid)
        received = [a for a in activities if a.activity_type == ActivityType.EMAIL_RECEIVED]
        assert len(received) == 1

    def test_unmatched_emails_counted(self, tmp_path: Path, memory_db: Database):
        """Emails to unknown addresses are counted as unmatched."""
        csv_file = tmp_path / "sent.csv"
        csv_file.write_text(
            "To,Subject,Body,Sent\n" "unknown@nowhere.com,Hello,Test,2026-02-10\n",
            encoding="utf-8",
        )

        importer = EmailCSVImporter(memory_db)
        result = importer.import_emails(csv_file, direction="sent")

        assert result.total_emails == 1
        assert result.matched_emails == 0
        assert result.unmatched_emails == 1
        assert result.activities_created == 0

    def test_deduplicates_on_reimport(self, tmp_path: Path, memory_db: Database):
        """Importing the same CSV twice doesn't create duplicate activities."""
        _setup_prospect_with_email(memory_db, "dedup@example.com")

        csv_file = tmp_path / "sent.csv"
        csv_file.write_text(
            "To,Subject,Body,Sent\n" "dedup@example.com,Same Email,Same body,2026-02-10\n",
            encoding="utf-8",
        )

        importer = EmailCSVImporter(memory_db)

        first = importer.import_emails(csv_file, direction="sent")
        assert first.activities_created == 1

        second = importer.import_emails(csv_file, direction="sent")
        assert second.activities_created == 0

    def test_mixed_matched_and_unmatched(self, tmp_path: Path, memory_db: Database):
        """Import with some matched and some unmatched emails."""
        _setup_prospect_with_email(memory_db, "known@example.com", "Known", "Person")

        csv_file = tmp_path / "sent.csv"
        csv_file.write_text(
            "To,Subject,Body,Sent\n"
            "known@example.com,To Known,Body 1,2026-02-10\n"
            "unknown@example.com,To Unknown,Body 2,2026-02-10\n",
            encoding="utf-8",
        )

        importer = EmailCSVImporter(memory_db)
        result = importer.import_emails(csv_file, direction="sent")

        assert result.total_emails == 2
        assert result.matched_emails == 1
        assert result.unmatched_emails == 1
        assert result.activities_created == 1

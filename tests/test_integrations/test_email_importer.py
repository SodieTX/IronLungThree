"""Tests for email CSV importer."""

from pathlib import Path

import pytest

from src.db.models import ActivityType, ContactMethod, ContactMethodType
from src.integrations.email_importer import EmailCSVImporter, EmailImportResult


class TestParseOutlookCSV:
    """Test CSV parsing."""

    def test_parse_standard_outlook_csv(self, populated_db, tmp_path):
        """Parses standard Outlook CSV format."""
        csv_path = tmp_path / "emails.csv"
        csv_path.write_text(
            "From,To,Subject,Body,Received\n"
            "john@acme.com,jeff@nexys.com,Re: Hello,Thanks for reaching out,2026-01-15\n"
            "jane@test.com,jeff@nexys.com,Demo request,Want a demo,2026-01-16\n"
        )
        importer = EmailCSVImporter(populated_db)
        rows = importer._parse_outlook_csv(csv_path)
        assert len(rows) == 2
        assert rows[0]["from"] == "john@acme.com"
        assert rows[0]["subject"] == "Re: Hello"

    def test_parse_empty_file(self, populated_db, tmp_path):
        """Handles empty CSV gracefully."""
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("From,To,Subject\n")
        importer = EmailCSVImporter(populated_db)
        rows = importer._parse_outlook_csv(csv_path)
        assert rows == []

    def test_parse_missing_file(self, populated_db, tmp_path):
        """Handles missing file gracefully."""
        importer = EmailCSVImporter(populated_db)
        rows = importer._parse_outlook_csv(tmp_path / "nope.csv")
        assert rows == []

    def test_parse_alternate_column_names(self, populated_db, tmp_path):
        """Handles alternate Outlook column names."""
        csv_path = tmp_path / "alt.csv"
        csv_path.write_text(
            "Sender,Recipients,Subject,Body Preview,Sent Date\n"
            "john@acme.com,jeff@nexys.com,Hello,Preview text,2026-01-15\n"
        )
        importer = EmailCSVImporter(populated_db)
        rows = importer._parse_outlook_csv(csv_path)
        assert len(rows) == 1
        assert rows[0]["from"] == "john@acme.com"
        assert rows[0]["body"] == "Preview text"


class TestMatchToProspect:
    """Test prospect matching by email."""

    def test_match_by_email(self, populated_db):
        """Matches email to prospect via contact methods."""
        importer = EmailCSVImporter(populated_db)
        # john.doe@acme.com is in the populated_db fixture
        result = importer._match_to_prospect("john.doe@acme.com")
        # Should find a prospect (the unengaged one)
        assert result is not None

    def test_no_match(self, populated_db):
        """Returns None for unknown email."""
        importer = EmailCSVImporter(populated_db)
        result = importer._match_to_prospect("nobody@nowhere.com")
        assert result is None

    def test_handles_angle_bracket_format(self, populated_db):
        """Handles 'Name <email>' format."""
        importer = EmailCSVImporter(populated_db)
        result = importer._match_to_prospect("John Doe <john.doe@acme.com>")
        # Should extract the email and match
        assert result is not None

    def test_handles_empty_email(self, populated_db):
        """Returns None for empty string."""
        importer = EmailCSVImporter(populated_db)
        assert importer._match_to_prospect("") is None
        assert importer._match_to_prospect("not-an-email") is None


class TestImportEmails:
    """Test full import workflow."""

    def test_import_sent_emails(self, populated_db, tmp_path):
        """Imports sent emails and creates activities."""
        csv_path = tmp_path / "sent.csv"
        csv_path.write_text(
            "To,Subject,Body,Sent\n"
            "john.doe@acme.com,Follow up,Hey John,2026-01-15\n"
            "unknown@nowhere.com,Hello,Hi there,2026-01-16\n"
        )
        importer = EmailCSVImporter(populated_db)
        result = importer.import_emails(csv_path, direction="sent")

        assert result.total_emails == 2
        assert result.matched_emails == 1
        assert result.unmatched_emails == 1
        assert result.activities_created == 1

    def test_deduplicates_imports(self, populated_db, tmp_path):
        """Doesn't create duplicate activities on re-import."""
        csv_path = tmp_path / "sent.csv"
        csv_path.write_text(
            "To,Subject,Body,Sent\n"
            "john.doe@acme.com,Follow up,Hey John,2026-01-15\n"
        )
        importer = EmailCSVImporter(populated_db)

        # Import twice
        result1 = importer.import_emails(csv_path, direction="sent")
        result2 = importer.import_emails(csv_path, direction="sent")

        assert result1.activities_created == 1
        assert result2.activities_created == 0  # Deduped

    def test_import_received_emails(self, populated_db, tmp_path):
        """Imports received emails."""
        csv_path = tmp_path / "inbox.csv"
        csv_path.write_text(
            "From,Subject,Body,Received\n"
            "john.doe@acme.com,Re: Hello,Thanks,2026-01-20\n"
        )
        importer = EmailCSVImporter(populated_db)
        result = importer.import_emails(csv_path, direction="received")

        assert result.total_emails == 1
        assert result.matched_emails == 1
        assert result.activities_created == 1

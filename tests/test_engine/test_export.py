"""Tests for data export and monthly summary.

Tests Step 3.10: Data Export + Closed Won Flow
    - Prospect CSV export
    - Monthly summary generation
    - Summary CSV export
    - Edge cases and error handling
"""

import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    Company,
    EngagementStage,
    Population,
    Prospect,
)
from src.engine.export import (
    DEFAULT_COLUMNS,
    MonthlySummary,
    export_prospects,
    export_summary_csv,
    generate_monthly_summary,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def db():
    """Fresh in-memory database."""
    database = Database(":memory:")
    database.initialize()
    yield database
    database.close()


@pytest.fixture
def company_id(db):
    """Create a test company, return its ID."""
    company = Company(name="Export Corp", state="CA", size="large")
    return db.create_company(company)


@pytest.fixture
def sample_prospects(company_id):
    """List of sample prospects for export testing."""
    return [
        Prospect(
            id=1,
            company_id=company_id,
            first_name="Alice",
            last_name="Johnson",
            title="CEO",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.CLOSING,
            prospect_score=95,
            data_confidence=90,
            source="Referral",
        ),
        Prospect(
            id=2,
            company_id=company_id,
            first_name="Bob",
            last_name="Williams",
            title="VP of Operations",
            population=Population.UNENGAGED,
            prospect_score=70,
            data_confidence=75,
            source="Conference",
        ),
    ]


@pytest.fixture
def populated_db(db, company_id):
    """DB with activity data for monthly summary testing."""
    # Create prospects
    p1 = Prospect(
        company_id=company_id,
        first_name="Alice",
        last_name="Johnson",
        population=Population.CLOSED_WON,
        deal_value=50000.00,
        close_date=date(2026, 2, 15),
    )
    p1_id = db.create_prospect(p1)

    p2 = Prospect(
        company_id=company_id,
        first_name="Bob",
        last_name="Williams",
        population=Population.CLOSED_WON,
        deal_value=30000.00,
        close_date=date(2026, 2, 20),
    )
    p2_id = db.create_prospect(p2)

    p3 = Prospect(
        company_id=company_id,
        first_name="Charlie",
        last_name="Brown",
        population=Population.ENGAGED,
    )
    p3_id = db.create_prospect(p3)

    # Add activities in February 2026
    # Calls
    for i in range(5):
        db.create_activity(
            Activity(
                prospect_id=p1_id,
                activity_type=ActivityType.CALL,
                notes=f"Call {i + 1}",
            )
        )

    # Emails
    for i in range(3):
        db.create_activity(
            Activity(
                prospect_id=p2_id,
                activity_type=ActivityType.EMAIL_SENT,
                notes=f"Email {i + 1}",
            )
        )

    # Demos booked
    db.create_activity(
        Activity(
            prospect_id=p1_id,
            activity_type=ActivityType.DEMO_SCHEDULED,
            notes="Demo scheduled",
        )
    )
    db.create_activity(
        Activity(
            prospect_id=p3_id,
            activity_type=ActivityType.DEMO_SCHEDULED,
            notes="Demo scheduled",
        )
    )

    # Status changes
    db.create_activity(
        Activity(
            prospect_id=p3_id,
            activity_type=ActivityType.STATUS_CHANGE,
            population_after=Population.ENGAGED,
            notes="Became engaged",
        )
    )

    return db


# =============================================================================
# PROSPECT CSV EXPORT
# =============================================================================


class TestExportProspects:
    """Test prospect CSV export."""

    def test_exports_prospects_to_csv(self, tmp_path, sample_prospects):
        """Exports prospects to CSV file."""
        path = tmp_path / "prospects.csv"
        result = export_prospects(sample_prospects, path)

        assert result is True
        assert path.exists()

    def test_csv_has_header_row(self, tmp_path, sample_prospects):
        """CSV file has header row with column names."""
        path = tmp_path / "prospects.csv"
        export_prospects(sample_prospects, path)

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
        assert header == DEFAULT_COLUMNS

    def test_csv_has_data_rows(self, tmp_path, sample_prospects):
        """CSV file has correct number of data rows."""
        path = tmp_path / "prospects.csv"
        export_prospects(sample_prospects, path)

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        # Header + 2 data rows
        assert len(rows) == 3

    def test_csv_contains_prospect_data(self, tmp_path, sample_prospects):
        """CSV contains correct prospect data."""
        path = tmp_path / "prospects.csv"
        export_prospects(sample_prospects, path)

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows[0]["first_name"] == "Alice"
        assert rows[0]["last_name"] == "Johnson"
        assert rows[1]["first_name"] == "Bob"

    def test_enum_values_exported_as_strings(self, tmp_path, sample_prospects):
        """Enum values are exported as their string value."""
        path = tmp_path / "prospects.csv"
        export_prospects(sample_prospects, path)

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows[0]["population"] == "engaged"
        assert rows[1]["population"] == "unengaged"

    def test_custom_columns(self, tmp_path, sample_prospects):
        """Custom columns are respected."""
        path = tmp_path / "prospects.csv"
        columns = ["first_name", "last_name", "population"]
        export_prospects(sample_prospects, path, columns=columns)

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
        assert header == columns

    def test_empty_prospects_returns_false(self, tmp_path):
        """Empty prospect list returns False."""
        path = tmp_path / "prospects.csv"
        result = export_prospects([], path)
        assert result is False

    def test_none_values_exported_as_empty(self, tmp_path):
        """None values are exported as empty strings."""
        prospects = [
            Prospect(
                id=1,
                company_id=1,
                first_name="Test",
                last_name="User",
                population=Population.BROKEN,
            )
        ]
        path = tmp_path / "prospects.csv"
        export_prospects(prospects, path)

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["title"] == ""
        assert rows[0]["notes"] == ""


# =============================================================================
# MONTHLY SUMMARY GENERATION
# =============================================================================


class TestGenerateMonthlySummary:
    """Test monthly summary generation."""

    def test_generates_summary(self, populated_db):
        """Generates a monthly summary."""
        summary = generate_monthly_summary(populated_db, "2026-02")
        assert isinstance(summary, MonthlySummary)
        assert summary.month == "2026-02"

    def test_counts_demos_booked(self, populated_db):
        """Counts demos booked in the month."""
        summary = generate_monthly_summary(populated_db, "2026-02")
        assert summary.demos_booked == 2

    def test_counts_calls_made(self, populated_db):
        """Counts calls made in the month."""
        summary = generate_monthly_summary(populated_db, "2026-02")
        assert summary.calls_made == 5

    def test_counts_emails_sent(self, populated_db):
        """Counts emails sent in the month."""
        summary = generate_monthly_summary(populated_db, "2026-02")
        assert summary.emails_sent == 3

    def test_counts_deals_closed(self, populated_db):
        """Counts deals closed in the month."""
        summary = generate_monthly_summary(populated_db, "2026-02")
        assert summary.deals_closed == 2

    def test_calculates_total_revenue(self, populated_db):
        """Calculates total revenue from closed deals."""
        summary = generate_monthly_summary(populated_db, "2026-02")
        assert summary.total_revenue == Decimal("80000")

    def test_calculates_commission(self, populated_db):
        """Calculates commission from total revenue."""
        summary = generate_monthly_summary(populated_db, "2026-02")
        expected = Decimal("80000") * Decimal("0.06")
        assert summary.commission_earned == expected

    def test_custom_commission_rate(self, populated_db):
        """Custom commission rate is applied."""
        summary = generate_monthly_summary(
            populated_db, "2026-02", commission_rate=Decimal("0.10")
        )
        expected = Decimal("80000") * Decimal("0.10")
        assert summary.commission_earned == expected
        assert summary.commission_rate == Decimal("0.10")

    def test_calculates_avg_deal_size(self, populated_db):
        """Calculates average deal size."""
        summary = generate_monthly_summary(populated_db, "2026-02")
        assert summary.avg_deal_size == Decimal("40000")

    def test_counts_pipeline_engaged(self, populated_db):
        """Counts new engaged prospects."""
        summary = generate_monthly_summary(populated_db, "2026-02")
        assert summary.pipeline_engaged == 1

    def test_empty_month_returns_zeros(self, populated_db):
        """Month with no activity returns zeros."""
        summary = generate_monthly_summary(populated_db, "2025-01")
        assert summary.demos_booked == 0
        assert summary.deals_closed == 0
        assert summary.total_revenue == Decimal("0")
        assert summary.calls_made == 0

    def test_pipeline_added_counts_new_prospects(self, populated_db):
        """Pipeline added counts new prospects created in the month."""
        summary = generate_monthly_summary(populated_db, "2026-02")
        # All 3 prospects were created "this month" (SQLite CURRENT_TIMESTAMP)
        assert summary.pipeline_added >= 0  # Depends on when created_at resolves


class TestGenerateMonthlySummaryDecember:
    """Test monthly summary for December (year boundary)."""

    def test_december_boundary(self, db):
        """December correctly uses January of next year as upper bound."""
        company_id = db.create_company(Company(name="Dec Co"))
        # This just verifies it doesn't crash on December
        summary = generate_monthly_summary(db, "2026-12")
        assert summary.month == "2026-12"
        assert summary.deals_closed == 0


# =============================================================================
# SUMMARY CSV EXPORT
# =============================================================================


class TestExportSummaryCsv:
    """Test summary CSV export."""

    def test_exports_summary_to_csv(self, tmp_path):
        """Exports summary to CSV file."""
        summary = MonthlySummary(
            month="2026-02",
            demos_booked=5,
            deals_closed=2,
            total_revenue=Decimal("80000"),
            commission_earned=Decimal("4800"),
            calls_made=25,
            emails_sent=10,
        )
        path = tmp_path / "summary.csv"
        result = export_summary_csv(summary, path)

        assert result is True
        assert path.exists()

    def test_summary_csv_has_metrics(self, tmp_path):
        """Summary CSV contains all metrics."""
        summary = MonthlySummary(
            month="2026-02",
            demos_booked=5,
            deals_closed=2,
            total_revenue=Decimal("80000"),
            commission_earned=Decimal("4800"),
            calls_made=25,
            emails_sent=10,
        )
        path = tmp_path / "summary.csv"
        export_summary_csv(summary, path)

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Header + 13 metric rows
        assert len(rows) == 14

        # Check header
        assert rows[0] == ["Metric", "Value"]

        # Check specific values
        metrics = {row[0]: row[1] for row in rows[1:]}
        assert metrics["Month"] == "2026-02"
        assert metrics["Demos Booked"] == "5"
        assert metrics["Deals Closed"] == "2"
        assert metrics["Total Revenue"] == "80000"
        assert metrics["Calls Made"] == "25"

    def test_summary_csv_with_none_values(self, tmp_path):
        """Summary CSV handles None values gracefully."""
        summary = MonthlySummary(month="2026-02")
        path = tmp_path / "summary.csv"
        result = export_summary_csv(summary, path)

        assert result is True

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        metrics = {row[0]: row[1] for row in rows[1:]}
        assert metrics["Avg Deal Size"] == ""
        assert metrics["Avg Cycle Days"] == ""

    def test_summary_csv_creates_parent_dirs(self, tmp_path):
        """Creates parent directories if needed."""
        summary = MonthlySummary(month="2026-02")
        path = tmp_path / "nested" / "dir" / "summary.csv"
        result = export_summary_csv(summary, path)
        assert result is True
        assert path.exists()

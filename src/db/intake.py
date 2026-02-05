"""Import intake funnel with deduplication and DNC protection.

Provides:
    - Three-pass deduplication (email, fuzzy name+company, phone)
    - Hard DNC blocking
    - Completeness assessment
    - Import preview before commit

Usage:
    from src.db.intake import IntakeFunnel

    funnel = IntakeFunnel(db)
    preview = funnel.analyze(records)
    # Show preview to user...
    result = funnel.commit(preview)
"""

from dataclasses import dataclass, field
from typing import Optional
from difflib import SequenceMatcher

from src.db.database import Database
from src.db.models import (
    Population,
    Prospect,
    ContactMethod,
    ContactMethodType,
    ImportSource,
    normalize_company_name,
    assess_completeness,
)
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ImportRecord:
    """A single record from import file.

    Attributes:
        first_name: First name
        last_name: Last name
        email: Email address
        phone: Phone number
        company_name: Company name
        title: Job title
        state: State code
        source: Lead source
        notes: Any notes
        raw_data: Original row data
    """

    first_name: str = ""
    last_name: str = ""
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: str = ""
    title: Optional[str] = None
    state: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    raw_data: Optional[dict] = None


@dataclass
class AnalysisResult:
    """Result of analyzing a single import record.

    Attributes:
        record: The import record
        status: new, duplicate, merge, needs_review, blocked_dnc, incomplete
        matched_prospect_id: ID if matched to existing prospect
        match_reason: Why it matched (email, fuzzy_name, phone)
        match_confidence: Match confidence for fuzzy matches
    """

    record: ImportRecord
    status: str = "new"
    matched_prospect_id: Optional[int] = None
    match_reason: Optional[str] = None
    match_confidence: Optional[float] = None


@dataclass
class ImportPreview:
    """Preview of import before committing.

    Attributes:
        new_records: Records to create
        merge_records: Records to merge into existing
        needs_review: Records needing manual review (phone matches)
        blocked_dnc: Records blocked by DNC match
        incomplete: Records missing required data
        source_name: Name for import source
        filename: Original filename
    """

    new_records: list[AnalysisResult] = field(default_factory=list)
    merge_records: list[AnalysisResult] = field(default_factory=list)
    needs_review: list[AnalysisResult] = field(default_factory=list)
    blocked_dnc: list[AnalysisResult] = field(default_factory=list)
    incomplete: list[AnalysisResult] = field(default_factory=list)
    source_name: str = ""
    filename: str = ""

    @property
    def total_records(self) -> int:
        """Total records analyzed."""
        return (
            len(self.new_records)
            + len(self.merge_records)
            + len(self.needs_review)
            + len(self.blocked_dnc)
            + len(self.incomplete)
        )

    @property
    def can_import(self) -> bool:
        """Whether there are records to import."""
        return len(self.new_records) > 0 or len(self.merge_records) > 0


@dataclass
class ImportResult:
    """Result of committing an import.

    Attributes:
        imported_count: New records created
        merged_count: Records merged into existing
        broken_count: Records marked as broken
        source_id: ID of created import source record
    """

    imported_count: int = 0
    merged_count: int = 0
    broken_count: int = 0
    source_id: Optional[int] = None


class IntakeFunnel:
    """Import intake with deduplication and DNC protection.

    Three-pass deduplication:
        1. Exact email match → same person, merge
        2. Fuzzy company + name (>85%) → potential duplicate
        3. Phone match → needs manual review (shared lines)

    DNC Protection:
        - Checked BEFORE dedup
        - ANY match to DNC = blocked
        - NEVER merged, NEVER updated, NEVER reactivated
    """

    def __init__(self, db: Database):
        """Initialize intake funnel.

        Args:
            db: Database instance
        """
        self.db = db
        self.name_similarity_threshold = 0.85

    def analyze(
        self,
        records: list[ImportRecord],
        source_name: str = "",
        filename: str = "",
    ) -> ImportPreview:
        """Analyze records for dedup and DNC.

        Does NOT modify database.

        Args:
            records: Import records to analyze
            source_name: Name for import source
            filename: Original filename

        Returns:
            ImportPreview with categorized records
        """
        raise NotImplementedError("Phase 1, Step 1.13")

    def commit(self, preview: ImportPreview) -> ImportResult:
        """Commit analyzed records to database.

        Creates prospects, contact methods, activities, import source.

        Args:
            preview: Analyzed import preview

        Returns:
            ImportResult with counts
        """
        raise NotImplementedError("Phase 1, Step 1.13")

    def _check_dnc(self, record: ImportRecord) -> bool:
        """Check if record matches any DNC.

        Returns True if blocked by DNC.
        """
        raise NotImplementedError("Phase 1, Step 1.13")

    def _check_email_match(self, email: str) -> Optional[int]:
        """Check for exact email match.

        Returns prospect ID if found.
        """
        raise NotImplementedError("Phase 1, Step 1.13")

    def _check_fuzzy_match(
        self,
        first_name: str,
        last_name: str,
        company_name: str,
    ) -> Optional[tuple[int, float]]:
        """Check for fuzzy name + company match.

        Returns (prospect_id, similarity) if above threshold.
        """
        raise NotImplementedError("Phase 1, Step 1.13")

    def _check_phone_match(self, phone: str) -> Optional[int]:
        """Check for phone match.

        Returns prospect ID if found (for manual review).
        """
        raise NotImplementedError("Phase 1, Step 1.13")

    @staticmethod
    def name_similarity(name1: str, name2: str) -> float:
        """Calculate name similarity ratio.

        Uses SequenceMatcher for fuzzy matching.

        Args:
            name1: First name
            name2: Second name

        Returns:
            Similarity ratio 0.0 to 1.0
        """
        return SequenceMatcher(None, name1.lower(), name2.lower()).ratio()

    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normalize phone to digits only.

        Args:
            phone: Phone number in any format

        Returns:
            Digits only (e.g., "7135551234")
        """
        return "".join(c for c in phone if c.isdigit())

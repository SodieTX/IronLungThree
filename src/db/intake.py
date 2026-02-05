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
from difflib import SequenceMatcher
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import (
    ContactMethod,
    ContactMethodType,
    ImportSource,
    Population,
    Prospect,
    assess_completeness,
    normalize_company_name,
)

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
        preview = ImportPreview(source_name=source_name, filename=filename)

        for record in records:
            result = AnalysisResult(record=record)

            # Check for incomplete data (need at least first OR last name)
            if not record.first_name and not record.last_name:
                result.status = "incomplete"
                preview.incomplete.append(result)
                continue

            # DNC check FIRST - before anything else
            if self._check_dnc(record):
                result.status = "blocked_dnc"
                preview.blocked_dnc.append(result)
                continue

            # Pass 1: Exact email match
            if record.email:
                matched_id = self._check_email_match(record.email)
                if matched_id is not None:
                    result.status = "merge"
                    result.matched_prospect_id = matched_id
                    result.match_reason = "email"
                    result.match_confidence = 1.0
                    preview.merge_records.append(result)
                    continue

            # Pass 2: Fuzzy name + company match
            if record.first_name and record.last_name and record.company_name:
                fuzzy_result = self._check_fuzzy_match(
                    record.first_name, record.last_name, record.company_name
                )
                if fuzzy_result is not None:
                    matched_id, confidence = fuzzy_result
                    result.status = "merge"
                    result.matched_prospect_id = matched_id
                    result.match_reason = "fuzzy_name"
                    result.match_confidence = confidence
                    preview.merge_records.append(result)
                    continue

            # Pass 3: Phone match -> needs manual review
            if record.phone:
                phone_matched_id = self._check_phone_match(record.phone)
                if phone_matched_id is not None:
                    result.status = "needs_review"
                    result.matched_prospect_id = phone_matched_id
                    result.match_reason = "phone"
                    preview.needs_review.append(result)
                    continue

            # No match -> new record
            result.status = "new"
            preview.new_records.append(result)

        logger.info(
            "Import analysis complete",
            extra={"context": {
                "total": preview.total_records,
                "new": len(preview.new_records),
                "merge": len(preview.merge_records),
                "review": len(preview.needs_review),
                "dnc_blocked": len(preview.blocked_dnc),
                "incomplete": len(preview.incomplete),
            }},
        )

        return preview

    def commit(self, preview: ImportPreview) -> ImportResult:
        """Commit analyzed records to database.

        Creates prospects, contact methods, activities, import source.

        Args:
            preview: Analyzed import preview

        Returns:
            ImportResult with counts
        """
        from src.db.models import Activity, ActivityType, Company

        result = ImportResult()

        # Process new records
        for analysis in preview.new_records:
            record = analysis.record

            # Find or create company
            company_id = self._get_or_create_company(record)

            # Determine population based on completeness
            has_email = record.email is not None and record.email != ""
            has_phone = record.phone is not None and record.phone != ""
            population = Population.UNENGAGED if (has_email and has_phone) else Population.BROKEN

            if population == Population.BROKEN:
                result.broken_count += 1

            # Create prospect
            prospect = Prospect(
                company_id=company_id,
                first_name=record.first_name,
                last_name=record.last_name,
                title=record.title,
                population=population,
                source=record.source or preview.source_name,
                notes=record.notes,
            )
            prospect_id = self.db.create_prospect(prospect)

            # Create contact methods
            if record.email:
                self.db.create_contact_method(ContactMethod(
                    prospect_id=prospect_id,
                    type=ContactMethodType.EMAIL,
                    value=record.email.lower(),
                    is_primary=True,
                    source=preview.source_name,
                ))

            if record.phone:
                self.db.create_contact_method(ContactMethod(
                    prospect_id=prospect_id,
                    type=ContactMethodType.PHONE,
                    value=record.phone,
                    is_primary=not record.email,
                    source=preview.source_name,
                ))

            # Log import activity
            self.db.create_activity(Activity(
                prospect_id=prospect_id,
                activity_type=ActivityType.IMPORT,
                notes=f"Imported from {preview.source_name or preview.filename}",
                created_by="system",
            ))

            result.imported_count += 1

        # Process merge records
        for analysis in preview.merge_records:
            record = analysis.record
            prospect_id = analysis.matched_prospect_id
            if prospect_id is None:
                continue

            prospect = self.db.get_prospect(prospect_id)
            if prospect is None:
                continue

            # Update fields that are empty in existing record
            updated = False
            if not prospect.title and record.title:
                prospect.title = record.title
                updated = True
            if record.notes and not prospect.notes:
                prospect.notes = record.notes
                updated = True

            if updated:
                self.db.update_prospect(prospect)

            # Add any new contact methods
            existing_methods = self.db.get_contact_methods(prospect_id)
            existing_emails = {
                m.value.lower() for m in existing_methods
                if m.type == ContactMethodType.EMAIL
            }
            existing_phones = {
                "".join(c for c in m.value if c.isdigit())
                for m in existing_methods if m.type == ContactMethodType.PHONE
            }

            if record.email and record.email.lower() not in existing_emails:
                self.db.create_contact_method(ContactMethod(
                    prospect_id=prospect_id,
                    type=ContactMethodType.EMAIL,
                    value=record.email.lower(),
                    source=preview.source_name,
                ))

            if record.phone:
                phone_digits = "".join(c for c in record.phone if c.isdigit())
                if phone_digits not in existing_phones:
                    self.db.create_contact_method(ContactMethod(
                        prospect_id=prospect_id,
                        type=ContactMethodType.PHONE,
                        value=record.phone,
                        source=preview.source_name,
                    ))

            # Log merge activity
            self.db.create_activity(Activity(
                prospect_id=prospect_id,
                activity_type=ActivityType.ENRICHMENT,
                notes=(
                    f"Merged from import: {preview.source_name or preview.filename}"
                    f" (match: {analysis.match_reason})"
                ),
                created_by="system",
            ))

            result.merged_count += 1

        # Create import source record
        source = ImportSource(
            source_name=preview.source_name,
            filename=preview.filename,
            total_records=preview.total_records,
            imported_records=result.imported_count,
            duplicate_records=result.merged_count,
            broken_records=result.broken_count,
            dnc_blocked_records=len(preview.blocked_dnc),
        )
        result.source_id = self.db.create_import_source(source)

        logger.info(
            "Import committed",
            extra={"context": {
                "imported": result.imported_count,
                "merged": result.merged_count,
                "broken": result.broken_count,
                "source_id": result.source_id,
            }},
        )

        return result

    def _get_or_create_company(self, record: ImportRecord) -> int:
        """Find or create company for an import record."""
        from src.db.models import Company

        if not record.company_name:
            company = Company(name="Unknown", state=record.state)
            return self.db.create_company(company)

        existing = self.db.get_company_by_normalized_name(record.company_name)
        if existing and existing.id is not None:
            return existing.id

        company = Company(name=record.company_name, state=record.state)
        return self.db.create_company(company)

    def _check_dnc(self, record: ImportRecord) -> bool:
        """Check if record matches any DNC.

        Returns True if blocked by DNC.
        """
        if record.email and self.db.is_dnc(email=record.email):
            return True
        if record.phone and self.db.is_dnc(phone=record.phone):
            return True
        return False

    def _check_email_match(self, email: str) -> Optional[int]:
        """Check for exact email match.

        Returns prospect ID if found.
        """
        return self.db.find_prospect_by_email(email)

    def _check_fuzzy_match(
        self,
        first_name: str,
        last_name: str,
        company_name: str,
    ) -> Optional[tuple[int, float]]:
        """Check for fuzzy name + company match.

        Returns (prospect_id, similarity) if above threshold.
        """
        existing_company = self.db.get_company_by_normalized_name(company_name)
        if existing_company is None or existing_company.id is None:
            return None

        prospects = self.db.get_prospects(company_id=existing_company.id, limit=500)
        full_name = f"{first_name} {last_name}".strip()

        for prospect in prospects:
            existing_name = prospect.full_name
            similarity = self.name_similarity(full_name, existing_name)
            if similarity >= self.name_similarity_threshold:
                return (prospect.id, similarity)

        return None

    def _check_phone_match(self, phone: str) -> Optional[int]:
        """Check for phone match.

        Returns prospect ID if found (for manual review).
        """
        return self.db.find_prospect_by_phone(phone)

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

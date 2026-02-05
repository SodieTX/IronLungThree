"""Data models and enumerations for IronLung 3.

All enums stored as TEXT in SQLite.
Dataclasses use frozen=False for mutability during processing.

This module defines:
    - Enumerations for all categorical fields
    - Dataclasses for database records
    - Utility functions (normalization, timezone lookup, completeness)
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

# =============================================================================
# ENUMERATIONS
# =============================================================================


class Population(str, Enum):
    """Where a prospect lives in the pipeline.

    Values:
        BROKEN: Missing phone or email, needs research
        UNENGAGED: Complete data, Jeff is chasing (system-paced)
        ENGAGED: Showed interest (prospect-paced)
        PARKED: Date-specific pause, auto-reactivates
        DEAD_DNC: Do Not Contact - PERMANENT, ABSOLUTE
        LOST: Went with competitor or not buying
        PARTNERSHIP: Non-prospect relationship contact
        CLOSED_WON: Deal closed successfully
    """

    BROKEN = "broken"
    UNENGAGED = "unengaged"
    ENGAGED = "engaged"
    PARKED = "parked"
    DEAD_DNC = "dead_dnc"
    LOST = "lost"
    PARTNERSHIP = "partnership"
    CLOSED_WON = "closed_won"


class EngagementStage(str, Enum):
    """Stage within ENGAGED population.

    Only used when population is ENGAGED.
    Tracks progress from initial interest to closing.
    """

    PRE_DEMO = "pre_demo"
    DEMO_SCHEDULED = "demo_scheduled"
    POST_DEMO = "post_demo"
    CLOSING = "closing"


class ActivityType(str, Enum):
    """Type of activity logged."""

    CALL = "call"
    VOICEMAIL = "voicemail"
    EMAIL_SENT = "email_sent"
    EMAIL_RECEIVED = "email_received"
    DEMO = "demo"
    DEMO_SCHEDULED = "demo_scheduled"
    DEMO_COMPLETED = "demo_completed"
    NOTE = "note"
    STATUS_CHANGE = "status_change"
    SKIP = "skip"
    DEFER = "defer"
    IMPORT = "import"
    ENRICHMENT = "enrichment"
    VERIFICATION = "verification"
    REMINDER = "reminder"
    TASK = "task"


class ActivityOutcome(str, Enum):
    """Outcome of an activity."""

    NO_ANSWER = "no_answer"
    LEFT_VM = "left_vm"
    SPOKE_WITH = "spoke_with"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    NOT_NOW = "not_now"
    DEMO_SET = "demo_set"
    DEMO_COMPLETED = "demo_completed"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    BOUNCED = "bounced"
    REPLIED = "replied"
    OOO = "ooo"
    REFERRAL = "referral"


class LostReason(str, Enum):
    """Reason a prospect was lost."""

    LOST_TO_COMPETITOR = "lost_to_competitor"
    NOT_BUYING = "not_buying"
    TIMING = "timing"
    BUDGET = "budget"
    OUT_OF_BUSINESS = "out_of_business"


class ContactMethodType(str, Enum):
    """Type of contact method."""

    EMAIL = "email"
    PHONE = "phone"


class AttemptType(str, Enum):
    """Type of outreach attempt.

    PERSONAL: Jeff's direct outreach
    AUTOMATED: System-sent nurture email
    """

    PERSONAL = "personal"
    AUTOMATED = "automated"


class ResearchStatus(str, Enum):
    """Status of autonomous research task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class IntelCategory(str, Enum):
    """Category of intel nugget."""

    PAIN_POINT = "pain_point"
    COMPETITOR = "competitor"
    LOAN_TYPE = "loan_type"
    DECISION_TIMELINE = "decision_timeline"
    KEY_FACT = "key_fact"


# =============================================================================
# TIMEZONE LOOKUP
# =============================================================================

STATE_TO_TIMEZONE: dict[str, str] = {
    "AL": "central",
    "AK": "alaska",
    "AZ": "mountain",
    "AR": "central",
    "CA": "pacific",
    "CO": "mountain",
    "CT": "eastern",
    "DE": "eastern",
    "FL": "eastern",
    "GA": "eastern",
    "HI": "hawaii",
    "ID": "mountain",
    "IL": "central",
    "IN": "eastern",
    "IA": "central",
    "KS": "central",
    "KY": "eastern",
    "LA": "central",
    "ME": "eastern",
    "MD": "eastern",
    "MA": "eastern",
    "MI": "eastern",
    "MN": "central",
    "MS": "central",
    "MO": "central",
    "MT": "mountain",
    "NE": "central",
    "NV": "pacific",
    "NH": "eastern",
    "NJ": "eastern",
    "NM": "mountain",
    "NY": "eastern",
    "NC": "eastern",
    "ND": "central",
    "OH": "eastern",
    "OK": "central",
    "OR": "pacific",
    "PA": "eastern",
    "RI": "eastern",
    "SC": "eastern",
    "SD": "central",
    "TN": "central",
    "TX": "central",
    "UT": "mountain",
    "VT": "eastern",
    "VA": "eastern",
    "WA": "pacific",
    "WV": "eastern",
    "WI": "central",
    "WY": "mountain",
    # DC
    "DC": "eastern",
}


def timezone_from_state(state: Optional[str]) -> str:
    """Return timezone for state code.

    Args:
        state: Two-letter state code (e.g., "TX")

    Returns:
        Timezone string (e.g., "central"). Default: "central"
    """
    if not state:
        return "central"
    return STATE_TO_TIMEZONE.get(state.upper().strip(), "central")


# =============================================================================
# NORMALIZATION
# =============================================================================

# Legal suffixes to strip (NOT business terms like Holdings, Capital, etc.)
LEGAL_SUFFIXES = [
    r",?\s*llc\.?$",
    r",?\s*l\.l\.c\.?$",
    r",?\s*inc\.?$",
    r",?\s*incorporated$",
    r",?\s*corp\.?$",
    r",?\s*corporation$",
    r",?\s*ltd\.?$",
    r",?\s*limited$",
    r",?\s*lp\.?$",
    r",?\s*l\.p\.?$",
    r",?\s*co\.?$",
    r",?\s*company$",
]


def normalize_company_name(name: str) -> str:
    """Normalize company name for deduplication.

    Strips ONLY legal entity suffixes (LLC, Inc, Corp, etc.).
    Preserves business identity terms (Holdings, Capital, Group, etc.).

    Args:
        name: Company name to normalize

    Returns:
        Lowercase name with legal suffixes stripped

    Examples:
        >>> normalize_company_name("ABC Lending, LLC")
        'abc lending'
        >>> normalize_company_name("First National Holdings, Inc.")
        'first national holdings'
        >>> normalize_company_name("XYZ Capital Corp.")
        'xyz capital'
    """
    result = name.lower().strip()
    for pattern in LEGAL_SUFFIXES:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)
    return result.strip()


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass
class Company:
    """Company record.

    Attributes:
        id: Primary key
        name: Display name
        name_normalized: Normalized name for dedup (auto-generated)
        domain: Company website domain
        loan_types: JSON array of loan types
        size: Company size (small/medium/large/enterprise)
        state: Two-letter state code
        timezone: Timezone (auto-assigned from state)
        notes: Company-level notes
        created_at: Record creation time
        updated_at: Last update time
    """

    id: Optional[int] = None
    name: str = ""
    name_normalized: str = ""
    domain: Optional[str] = None
    loan_types: Optional[str] = None  # JSON array
    size: Optional[str] = None
    state: Optional[str] = None
    timezone: str = "central"
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Prospect:
    """Prospect/contact record.

    Attributes:
        id: Primary key
        company_id: Foreign key to company
        first_name: First name
        last_name: Last name
        title: Job title
        population: Pipeline location
        engagement_stage: Stage within ENGAGED (if engaged)
        follow_up_date: Next follow-up datetime
        last_contact_date: Last contact date
        parked_month: Month to reactivate (YYYY-MM)
        attempt_count: Number of contact attempts
        prospect_score: Score 0-100
        data_confidence: Data confidence 0-100
        preferred_contact_method: email/phone/either
        source: Lead source
        referred_by_prospect_id: Referral tracking
        dead_reason: Why marked dead (DNC)
        dead_date: When marked dead
        lost_reason: Why lost
        lost_competitor: Which competitor
        lost_date: When lost
        deal_value: Closed deal value
        close_date: When deal closed
        close_notes: Close notes
        notes: Static context notes
        custom_fields: JSON blob for user fields
        created_at: Record creation time
        updated_at: Last update time
    """

    id: Optional[int] = None
    company_id: int = 0
    first_name: str = ""
    last_name: str = ""
    title: Optional[str] = None
    population: Population = Population.BROKEN
    engagement_stage: Optional[EngagementStage] = None
    follow_up_date: Optional[datetime] = None
    last_contact_date: Optional[date] = None
    parked_month: Optional[str] = None
    attempt_count: int = 0
    prospect_score: int = 0
    data_confidence: int = 0
    preferred_contact_method: Optional[str] = None
    source: Optional[str] = None
    referred_by_prospect_id: Optional[int] = None
    dead_reason: Optional[str] = None
    dead_date: Optional[date] = None
    lost_reason: Optional[LostReason] = None
    lost_competitor: Optional[str] = None
    lost_date: Optional[date] = None
    deal_value: Optional[Decimal] = None
    close_date: Optional[date] = None
    close_notes: Optional[str] = None
    notes: Optional[str] = None
    custom_fields: Optional[str] = None  # JSON blob
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def full_name(self) -> str:
        """Return full name."""
        return f"{self.first_name} {self.last_name}".strip()


@dataclass
class ContactMethod:
    """Contact method (email or phone).

    Attributes:
        id: Primary key
        prospect_id: Foreign key to prospect
        type: email or phone
        value: The email address or phone number
        label: work/personal/cell/main
        is_primary: Primary contact method flag
        is_verified: Verified flag
        verified_date: When verified
        confidence_score: Confidence 0-100
        is_suspect: Flagged as potentially wrong
        source: Where found
        created_at: Record creation time
    """

    id: Optional[int] = None
    prospect_id: int = 0
    type: ContactMethodType = ContactMethodType.EMAIL
    value: str = ""
    label: Optional[str] = None
    is_primary: bool = False
    is_verified: bool = False
    verified_date: Optional[date] = None
    confidence_score: int = 0
    is_suspect: bool = False
    source: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Activity:
    """Activity log entry.

    The notes field is the running log - the enduring memory.

    Attributes:
        id: Primary key
        prospect_id: Foreign key to prospect
        activity_type: Type of activity
        outcome: Activity outcome
        call_duration_seconds: Call duration (if call)
        population_before: Population before change
        population_after: Population after change
        stage_before: Engagement stage before
        stage_after: Engagement stage after
        email_subject: Email subject (if email)
        email_body: Email body (if email)
        follow_up_set: Follow-up date set by this activity
        attempt_type: personal or automated
        notes: Activity notes (the memory)
        created_by: user or system
        created_at: When logged
    """

    id: Optional[int] = None
    prospect_id: int = 0
    activity_type: ActivityType = ActivityType.NOTE
    outcome: Optional[ActivityOutcome] = None
    call_duration_seconds: Optional[int] = None
    population_before: Optional[Population] = None
    population_after: Optional[Population] = None
    stage_before: Optional[EngagementStage] = None
    stage_after: Optional[EngagementStage] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    follow_up_set: Optional[datetime] = None
    attempt_type: Optional[AttemptType] = None
    notes: Optional[str] = None
    created_by: str = "user"
    created_at: Optional[datetime] = None


@dataclass
class ImportSource:
    """Import batch tracking.

    Attributes:
        id: Primary key
        source_name: Name of the source
        filename: Original filename
        total_records: Total records in file
        imported_records: Records actually imported
        duplicate_records: Records merged as duplicates
        broken_records: Records missing data
        dnc_blocked_records: Records blocked by DNC
        import_date: When imported
    """

    id: Optional[int] = None
    source_name: str = ""
    filename: Optional[str] = None
    total_records: int = 0
    imported_records: int = 0
    duplicate_records: int = 0
    broken_records: int = 0
    dnc_blocked_records: int = 0
    import_date: Optional[datetime] = None


@dataclass
class ResearchTask:
    """Autonomous research queue entry.

    Attributes:
        id: Primary key
        prospect_id: Foreign key to prospect
        priority: Priority (higher = more urgent)
        status: Research status
        attempts: Number of research attempts
        last_attempt_date: When last attempted
        findings: JSON with research findings
    """

    id: Optional[int] = None
    prospect_id: int = 0
    priority: int = 0
    status: ResearchStatus = ResearchStatus.PENDING
    attempts: int = 0
    last_attempt_date: Optional[datetime] = None
    findings: Optional[str] = None  # JSON


@dataclass
class IntelNugget:
    """Extracted intel for call cheat sheets.

    Attributes:
        id: Primary key
        prospect_id: Foreign key to prospect
        category: Type of intel
        content: The intel content
        source_activity_id: Activity it was extracted from
        extracted_date: When extracted
    """

    id: Optional[int] = None
    prospect_id: int = 0
    category: IntelCategory = IntelCategory.KEY_FACT
    content: str = ""
    source_activity_id: Optional[int] = None
    extracted_date: Optional[datetime] = None


@dataclass
class ProspectTag:
    """User-defined tag on prospect.

    Tags are flexible labels: "hot-referral", "conference-lead", etc.
    No transition rules, don't affect cadence or DNC.

    Attributes:
        id: Primary key
        prospect_id: Foreign key to prospect
        tag_name: The tag
        created_at: When tagged
    """

    id: Optional[int] = None
    prospect_id: int = 0
    tag_name: str = ""
    created_at: Optional[datetime] = None


# =============================================================================
# COMPLETENESS ASSESSMENT
# =============================================================================


def assess_completeness(
    prospect: Prospect,
    contact_methods: list[ContactMethod],
) -> Population:
    """Assess if prospect has complete data.

    A prospect needs BOTH email AND phone to be complete.

    Args:
        prospect: The prospect
        contact_methods: Prospect's contact methods

    Returns:
        Population.UNENGAGED if complete, Population.BROKEN if missing data
    """
    has_email = any(m.type == ContactMethodType.EMAIL for m in contact_methods)
    has_phone = any(m.type == ContactMethodType.PHONE for m in contact_methods)

    if has_email and has_phone:
        return Population.UNENGAGED
    return Population.BROKEN

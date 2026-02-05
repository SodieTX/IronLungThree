"""Autonomous research for broken prospects.

Attempts to find missing contact information using free sources:
    1. Company website scraping (/about, /team, /contact)
    2. Email pattern detection
    3. Google Custom Search (100/day free)
    4. NMLS Lookup (licensed lenders)

The 90% Rule:
    - Auto-fill (90%+ confidence): Found on website with name match
    - Suggest (below 90%): Show Jeff, let him confirm

Honest expectations: Fixes 20-30% of broken records. Not 50-60%.

Usage:
    from src.engine.research import ResearchEngine

    engine = ResearchEngine(db)
    result = engine.research_prospect(prospect_id)
"""

from dataclasses import dataclass
from typing import Optional, List
from enum import Enum

from src.db.database import Database
from src.db.models import ResearchStatus
from src.integrations.google_search import GoogleSearchClient
from src.core.logging import get_logger

logger = get_logger(__name__)


class FindingConfidence(str, Enum):
    """Confidence level of research finding."""

    HIGH = "high"  # Auto-fill (90%+)
    MEDIUM = "medium"  # Suggest with context
    LOW = "low"  # Show what was found, low confidence


@dataclass
class ResearchFinding:
    """A single research finding.

    Attributes:
        field: Field found (email, phone)
        value: Found value
        confidence: Confidence level
        source: Where it was found
        source_url: URL where found
        context: Why we think it's valid
    """

    field: str
    value: str
    confidence: FindingConfidence
    source: str
    source_url: Optional[str] = None
    context: Optional[str] = None


@dataclass
class ResearchResult:
    """Result of researching a prospect.

    Attributes:
        prospect_id: Prospect researched
        findings: List of findings
        auto_fill: Findings to apply automatically
        suggestions: Findings needing confirmation
        search_links: Pre-built search links for manual research
    """

    prospect_id: int
    findings: list[ResearchFinding]
    auto_fill: list[ResearchFinding]
    suggestions: list[ResearchFinding]
    search_links: dict[str, str]  # name -> URL


class ResearchEngine:
    """Autonomous research for broken prospects.

    Runs during nightly cycle against broken records.
    """

    def __init__(self, db: Database, google_client: Optional[GoogleSearchClient] = None):
        """Initialize research engine.

        Args:
            db: Database instance
            google_client: Optional Google Search client
        """
        self.db = db
        self.google = google_client or GoogleSearchClient()

    def research_prospect(self, prospect_id: int) -> ResearchResult:
        """Run research on a broken prospect.

        Args:
            prospect_id: Prospect to research

        Returns:
            ResearchResult with findings
        """
        raise NotImplementedError("Phase 5, Step 5.1")

    def scrape_company_site(self, domain: str) -> list[ResearchFinding]:
        """Scrape company website for contact info.

        Checks /about, /team, /contact pages.

        Args:
            domain: Company domain

        Returns:
            List of findings
        """
        raise NotImplementedError("Phase 5, Step 5.1")

    def detect_email_pattern(
        self,
        domain: str,
        first_name: str,
        last_name: str,
    ) -> list[str]:
        """Generate likely email patterns.

        Common patterns:
            - firstname@domain
            - first.last@domain
            - firstl@domain
            - flast@domain

        Returns:
            List of possible email addresses
        """
        raise NotImplementedError("Phase 5, Step 5.1")

    def build_search_links(
        self,
        prospect_name: str,
        company_name: str,
    ) -> dict[str, str]:
        """Build pre-made search links for manual research.

        Returns:
            Dict of link_name -> URL
        """
        raise NotImplementedError("Phase 5, Step 5.1")

    def run_batch(self, limit: int = 50) -> int:
        """Run research on batch of broken prospects.

        Called during nightly cycle.

        Args:
            limit: Maximum prospects to research

        Returns:
            Number of prospects researched
        """
        raise NotImplementedError("Phase 5, Step 5.1")

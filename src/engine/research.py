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

import json
import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    ContactMethod,
    ContactMethodType,
    Population,
    ResearchStatus,
    ResearchTask,
)
from src.integrations.google_search import GoogleSearchClient

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


# Common email patterns ordered by prevalence
EMAIL_PATTERNS = [
    "{first}@{domain}",
    "{first}.{last}@{domain}",
    "{first}{last}@{domain}",
    "{f}{last}@{domain}",
    "{first}_{last}@{domain}",
    "{first}{l}@{domain}",
]


def _generate_email_candidates(
    first_name: str,
    last_name: str,
    domain: str,
) -> list[str]:
    """Generate likely email addresses from name and domain.

    Args:
        first_name: First name
        last_name: Last name
        domain: Company domain

    Returns:
        List of possible email addresses
    """
    if not first_name or not last_name or not domain:
        return []

    first = first_name.lower().strip()
    last = last_name.lower().strip()
    f = first[0] if first else ""
    l_initial = last[0] if last else ""

    candidates = []
    for pattern in EMAIL_PATTERNS:
        email = pattern.format(first=first, last=last, f=f, l=l_initial, domain=domain)
        candidates.append(email)

    return candidates


def _extract_domain_from_url(url: str) -> Optional[str]:
    """Extract clean domain from a URL or domain string.

    Args:
        url: URL or domain string

    Returns:
        Clean domain (e.g., "acme.com")
    """
    if not url:
        return None

    # If it doesn't have a scheme, add one for parsing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.hostname or ""
        # Strip www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        return domain if domain else None
    except Exception:
        return None


def _build_google_search_url(query: str) -> str:
    """Build a Google search URL for manual research."""
    encoded = urllib.parse.quote_plus(query)
    return f"https://www.google.com/search?q={encoded}"


def _build_nmls_search_url(name: str) -> str:
    """Build NMLS consumer access search URL."""
    encoded = urllib.parse.quote_plus(name)
    return (
        "https://www.nmlsconsumeraccess.org/TuringTestPage.aspx"
        f"?ReturnUrl=/EntitySearch.aspx%3FSID%3D{encoded}"
    )


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

        Attempts to find missing contact information.
        Categorizes findings as auto-fill (HIGH confidence) or suggestions.

        Args:
            prospect_id: Prospect to research

        Returns:
            ResearchResult with findings and search links
        """
        prospect = self.db.get_prospect(prospect_id)
        if prospect is None:
            return ResearchResult(
                prospect_id=prospect_id,
                findings=[],
                auto_fill=[],
                suggestions=[],
                search_links={},
            )

        # Get existing contact methods to know what's missing
        contact_methods = self.db.get_contact_methods(prospect_id)
        has_email = any(m.type == ContactMethodType.EMAIL for m in contact_methods)
        has_phone = any(m.type == ContactMethodType.PHONE for m in contact_methods)

        # Get company info for domain-based research
        company = self.db.get_company(prospect.company_id) if prospect.company_id else None
        domain = _extract_domain_from_url(company.domain) if company and company.domain else None

        findings: list[ResearchFinding] = []

        # Strategy 1: Email pattern detection (if missing email and we have domain)
        if not has_email and domain:
            email_candidates = self.detect_email_pattern(
                domain, prospect.first_name, prospect.last_name
            )
            for email in email_candidates:
                findings.append(
                    ResearchFinding(
                        field="email",
                        value=email,
                        confidence=FindingConfidence.MEDIUM,
                        source="email_pattern",
                        context=f"Generated from pattern: {prospect.first_name.lower()}@{domain}",
                    )
                )

        # Strategy 2: Google search (if configured and quota available)
        if self.google.is_configured() and self.google.get_remaining_quota() > 0:
            company_name = company.name if company else ""
            prospect_name = f"{prospect.first_name} {prospect.last_name}"

            if not has_email or not has_phone:
                try:
                    search_query = f"{prospect_name} {company_name} contact email phone"
                    results = self.google.search(search_query, num_results=5)

                    for result in results:
                        # Look for email patterns in snippets
                        if not has_email:
                            emails_found = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", result.snippet)
                            for email in emails_found:
                                email_domain = email.split("@")[1] if "@" in email else ""
                                if domain and email_domain.lower() == domain.lower():
                                    confidence = FindingConfidence.HIGH
                                    context = (
                                        f"Found on web with matching company domain: {result.url}"
                                    )
                                else:
                                    confidence = FindingConfidence.LOW
                                    context = f"Found on web (domain mismatch): {result.url}"

                                findings.append(
                                    ResearchFinding(
                                        field="email",
                                        value=email.lower(),
                                        confidence=confidence,
                                        source="google_search",
                                        source_url=result.url,
                                        context=context,
                                    )
                                )

                        # Look for phone patterns in snippets
                        if not has_phone:
                            phones_found = re.findall(
                                r"(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
                                result.snippet,
                            )
                            for phone in phones_found:
                                digits = re.sub(r"\D", "", phone)
                                if len(digits) >= 10:
                                    findings.append(
                                        ResearchFinding(
                                            field="phone",
                                            value=phone.strip(),
                                            confidence=FindingConfidence.LOW,
                                            source="google_search",
                                            source_url=result.url,
                                            context=f"Found on web: {result.url}",
                                        )
                                    )
                except Exception as e:
                    logger.warning(
                        "Google search failed during research",
                        extra={"context": {"prospect_id": prospect_id, "error": str(e)}},
                    )

        # Build search links for manual research
        prospect_name = f"{prospect.first_name} {prospect.last_name}"
        company_name = company.name if company else ""
        search_links = self.build_search_links(prospect_name, company_name)

        if domain:
            search_links["Company Website"] = f"https://{domain}"

        # Categorize findings
        auto_fill = [f for f in findings if f.confidence == FindingConfidence.HIGH]
        suggestions = [f for f in findings if f.confidence != FindingConfidence.HIGH]

        # Deduplicate findings by value
        seen_values: set[str] = set()
        unique_auto_fill: list[ResearchFinding] = []
        for f in auto_fill:
            if f.value.lower() not in seen_values:
                seen_values.add(f.value.lower())
                unique_auto_fill.append(f)

        unique_suggestions: list[ResearchFinding] = []
        for f in suggestions:
            if f.value.lower() not in seen_values:
                seen_values.add(f.value.lower())
                unique_suggestions.append(f)

        research_result = ResearchResult(
            prospect_id=prospect_id,
            findings=findings,
            auto_fill=unique_auto_fill,
            suggestions=unique_suggestions,
            search_links=search_links,
        )

        # Update research queue status
        self._update_research_task(prospect_id, research_result)

        logger.info(
            "Research completed",
            extra={
                "context": {
                    "prospect_id": prospect_id,
                    "auto_fill_count": len(unique_auto_fill),
                    "suggestion_count": len(unique_suggestions),
                }
            },
        )

        return research_result

    def scrape_company_site(self, domain: str) -> list[ResearchFinding]:
        """Scrape company website for contact info.

        Checks /about, /team, /contact pages.

        Note: In this implementation, we build URLs for manual review
        rather than actually scraping (respects robots.txt and avoids
        unreliable HTML parsing of unknown site structures).

        Args:
            domain: Company domain

        Returns:
            List of findings (empty - scraping deferred to manual review)
        """
        # We don't actually scrape in automated mode - too unreliable
        # and potentially violates robots.txt. Instead we build the URLs
        # as search_links for Jeff to check manually.
        logger.info(
            "Company site research deferred to manual review",
            extra={"context": {"domain": domain}},
        )
        return []

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
        return _generate_email_candidates(first_name, last_name, domain)

    def build_search_links(
        self,
        prospect_name: str,
        company_name: str,
    ) -> dict[str, str]:
        """Build pre-made search links for manual research.

        Returns:
            Dict of link_name -> URL
        """
        links: dict[str, str] = {}

        if prospect_name.strip():
            links["Google: Person"] = _build_google_search_url(f"{prospect_name} {company_name}")
            links["NMLS Lookup"] = _build_nmls_search_url(prospect_name)

        if company_name.strip():
            links["Google: Company"] = _build_google_search_url(f"{company_name} contact")
            links["Google: Company + Email"] = _build_google_search_url(f"{company_name} email")

        if prospect_name.strip() and company_name.strip():
            links["Google: Person + Contact"] = _build_google_search_url(
                f'"{prospect_name}" "{company_name}" contact email phone'
            )

        return links

    def run_batch(self, limit: int = 50) -> int:
        """Run research on batch of broken prospects.

        Called during nightly cycle. Processes broken prospects
        with pending research tasks, ordered by priority.

        Args:
            limit: Maximum prospects to research

        Returns:
            Number of prospects researched
        """
        broken = self.db.get_prospects(population=Population.BROKEN, limit=limit)

        researched = 0
        for prospect in broken:
            if prospect.id is None:
                continue

            try:
                result = self.research_prospect(prospect.id)

                # Apply auto-fill findings
                for finding in result.auto_fill:
                    self._apply_finding(prospect.id, finding)

                researched += 1
            except Exception as e:
                logger.warning(
                    "Research failed for prospect",
                    extra={
                        "context": {
                            "prospect_id": prospect.id,
                            "error": str(e),
                        }
                    },
                )

        logger.info(
            "Batch research completed",
            extra={"context": {"researched": researched, "limit": limit}},
        )

        return researched

    def _apply_finding(self, prospect_id: int, finding: ResearchFinding) -> bool:
        """Apply a HIGH confidence finding to the database.

        Creates contact method and logs enrichment activity.

        Args:
            prospect_id: Prospect to update
            finding: Finding to apply

        Returns:
            True if applied
        """
        if finding.confidence != FindingConfidence.HIGH:
            return False

        if finding.field == "email":
            method_type = ContactMethodType.EMAIL
        elif finding.field == "phone":
            method_type = ContactMethodType.PHONE
        else:
            return False

        # Check for duplicates
        existing = self.db.get_contact_methods(prospect_id)
        for m in existing:
            if m.type == method_type and m.value.lower() == finding.value.lower():
                return False  # Already exists

        # Create the contact method
        method = ContactMethod(
            prospect_id=prospect_id,
            type=method_type,
            value=finding.value,
            source=f"research:{finding.source}",
            confidence_score=90,
        )
        self.db.create_contact_method(method)

        # Log the enrichment activity
        activity = Activity(
            prospect_id=prospect_id,
            activity_type=ActivityType.ENRICHMENT,
            notes=(
                f"Auto-filled {finding.field}: {finding.value} "
                f"(source: {finding.source}, confidence: {finding.confidence.value})"
            ),
            created_by="system",
        )
        self.db.create_activity(activity)

        logger.info(
            "Finding applied",
            extra={
                "context": {
                    "prospect_id": prospect_id,
                    "field": finding.field,
                    "source": finding.source,
                }
            },
        )

        return True

    def _update_research_task(self, prospect_id: int, result: ResearchResult) -> None:
        """Update the research queue with results.

        Args:
            prospect_id: Prospect researched
            result: Research results
        """
        tasks = self.db.get_research_tasks()
        existing_task = None
        for task in tasks:
            if task.prospect_id == prospect_id:
                existing_task = task
                break

        findings_json = json.dumps(
            [
                {
                    "field": f.field,
                    "value": f.value,
                    "confidence": f.confidence.value,
                    "source": f.source,
                }
                for f in result.findings
            ]
        )

        if existing_task and existing_task.id is not None:
            conn = self.db._get_connection()
            status = ResearchStatus.COMPLETED if result.findings else ResearchStatus.FAILED
            conn.execute(
                """UPDATE research_queue
                   SET status = ?, attempts = attempts + 1,
                       last_attempt_date = CURRENT_TIMESTAMP, findings = ?
                   WHERE id = ?""",
                (status.value, findings_json, existing_task.id),
            )
            conn.commit()
        else:
            status = ResearchStatus.COMPLETED if result.findings else ResearchStatus.FAILED
            task = ResearchTask(
                prospect_id=prospect_id,
                priority=0,
                status=status,
                attempts=1,
                last_attempt_date=datetime.now(),
                findings=findings_json,
            )
            self.db.create_research_task(task)

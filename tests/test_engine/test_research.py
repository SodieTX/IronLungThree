"""Tests for autonomous research engine.

Tests Phase 5: Research Engine
    - Email candidate generation
    - Domain extraction from URLs
    - Google/NMLS search URL building
    - Email pattern detection
    - Search link generation
    - Prospect research with database
    - Batch research processing
    - Finding application logic
    - Company site scraping (deferred)
"""

from unittest.mock import MagicMock, patch

import pytest

from src.db.database import Database
from src.db.models import (
    Activity,
    ActivityType,
    Company,
    ContactMethod,
    ContactMethodType,
    Population,
    Prospect,
)
from src.engine.research import (
    FindingConfidence,
    ResearchEngine,
    ResearchFinding,
    ResearchResult,
    _build_google_search_url,
    _build_nmls_search_url,
    _extract_domain_from_url,
    _generate_email_candidates,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def memory_db():
    """In-memory database for fast tests."""
    db = Database(":memory:")
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def research_db(memory_db):
    """Database with a company and a broken prospect for research tests."""
    company = Company(
        name="Acme Lending LLC",
        domain="acmelending.com",
        state="TX",
        size="medium",
    )
    company_id = memory_db.create_company(company)

    prospect = Prospect(
        company_id=company_id,
        first_name="John",
        last_name="Doe",
        title="VP of Operations",
        population=Population.BROKEN,
        prospect_score=75,
        data_confidence=30,
        source="LinkedIn Import",
    )
    prospect_id = memory_db.create_prospect(prospect)

    # Add a phone but no email -- the prospect is "broken" because missing email
    phone = ContactMethod(
        prospect_id=prospect_id,
        type=ContactMethodType.PHONE,
        value="555-123-4567",
        label="work",
    )
    memory_db.create_contact_method(phone)

    return memory_db, company_id, prospect_id


@pytest.fixture
def mock_google():
    """Mock Google Search client that is not configured."""
    client = MagicMock()
    client.is_configured.return_value = False
    client.get_remaining_quota.return_value = 0
    return client


# =============================================================================
# _generate_email_candidates
# =============================================================================


class TestGenerateEmailCandidates:
    """Test email candidate generation from name and domain."""

    def test_valid_names(self):
        """Standard names produce expected email patterns."""
        candidates = _generate_email_candidates("John", "Doe", "acme.com")
        assert len(candidates) == 6
        assert "john@acme.com" in candidates
        assert "john.doe@acme.com" in candidates
        assert "johndoe@acme.com" in candidates
        assert "jdoe@acme.com" in candidates
        assert "john_doe@acme.com" in candidates
        assert "johnd@acme.com" in candidates

    def test_empty_first_name(self):
        """Empty first name returns empty list."""
        assert _generate_email_candidates("", "Doe", "acme.com") == []

    def test_empty_last_name(self):
        """Empty last name returns empty list."""
        assert _generate_email_candidates("John", "", "acme.com") == []

    def test_empty_domain(self):
        """Empty domain returns empty list."""
        assert _generate_email_candidates("John", "Doe", "") == []

    def test_all_empty(self):
        """All empty inputs return empty list."""
        assert _generate_email_candidates("", "", "") == []

    def test_names_lowercased(self):
        """Names are lowercased in email candidates."""
        candidates = _generate_email_candidates("JOHN", "DOE", "acme.com")
        for email in candidates:
            local_part = email.split("@")[0]
            assert local_part == local_part.lower()

    def test_names_stripped(self):
        """Leading/trailing whitespace is stripped from names."""
        candidates = _generate_email_candidates("  John  ", "  Doe  ", "acme.com")
        assert "john@acme.com" in candidates
        assert "john.doe@acme.com" in candidates

    def test_different_domain(self):
        """Domain is correctly included in all patterns."""
        candidates = _generate_email_candidates("Jane", "Smith", "bigbank.org")
        for email in candidates:
            assert email.endswith("@bigbank.org")


# =============================================================================
# _extract_domain_from_url
# =============================================================================


class TestExtractDomainFromUrl:
    """Test domain extraction from URLs."""

    def test_full_https_url(self):
        """Extract domain from full HTTPS URL."""
        assert _extract_domain_from_url("https://www.acme.com/about") == "acme.com"

    def test_full_http_url(self):
        """Extract domain from full HTTP URL."""
        assert _extract_domain_from_url("http://acme.com/contact") == "acme.com"

    def test_bare_domain(self):
        """Extract domain from bare domain string."""
        assert _extract_domain_from_url("acme.com") == "acme.com"

    def test_www_prefix_stripped(self):
        """www. prefix is stripped."""
        assert _extract_domain_from_url("www.acme.com") == "acme.com"

    def test_empty_string(self):
        """Empty string returns None."""
        assert _extract_domain_from_url("") is None

    def test_none_input(self):
        """None-like empty input returns None."""
        assert _extract_domain_from_url("") is None

    def test_domain_with_path(self):
        """Domain with path is correctly extracted."""
        assert _extract_domain_from_url("https://acme.com/team/leadership") == "acme.com"

    def test_subdomain(self):
        """Subdomain is preserved (only www. stripped)."""
        assert _extract_domain_from_url("https://app.acme.com") == "app.acme.com"


# =============================================================================
# _build_google_search_url
# =============================================================================


class TestBuildGoogleSearchUrl:
    """Test Google search URL building."""

    def test_simple_query(self):
        """Simple query is encoded."""
        url = _build_google_search_url("John Doe")
        assert url.startswith("https://www.google.com/search?q=")
        assert "John+Doe" in url

    def test_special_characters_encoded(self):
        """Special characters are URL-encoded."""
        url = _build_google_search_url('"John Doe" "Acme Corp" contact')
        assert "https://www.google.com/search?q=" in url
        # Quotes should be encoded
        assert "%22" in url

    def test_empty_query(self):
        """Empty query still produces a valid URL."""
        url = _build_google_search_url("")
        assert url == "https://www.google.com/search?q="


# =============================================================================
# _build_nmls_search_url
# =============================================================================


class TestBuildNmlsSearchUrl:
    """Test NMLS search URL building."""

    def test_url_contains_name(self):
        """Name is encoded in the NMLS URL."""
        url = _build_nmls_search_url("John Doe")
        assert "nmlsconsumeraccess.org" in url
        assert "John+Doe" in url or "John%20Doe" in url

    def test_url_structure(self):
        """URL has the expected base structure."""
        url = _build_nmls_search_url("Jane Smith")
        assert url.startswith("https://www.nmlsconsumeraccess.org/TuringTestPage.aspx")


# =============================================================================
# ResearchEngine.detect_email_pattern
# =============================================================================


class TestDetectEmailPattern:
    """Test email pattern detection via the engine."""

    def test_returns_candidates(self, memory_db, mock_google):
        """detect_email_pattern returns email candidates."""
        engine = ResearchEngine(memory_db, google_client=mock_google)
        results = engine.detect_email_pattern("acme.com", "John", "Doe")
        assert len(results) == 6
        assert "john@acme.com" in results

    def test_empty_name(self, memory_db, mock_google):
        """Empty name returns empty list."""
        engine = ResearchEngine(memory_db, google_client=mock_google)
        results = engine.detect_email_pattern("acme.com", "", "Doe")
        assert results == []


# =============================================================================
# ResearchEngine.build_search_links
# =============================================================================


class TestBuildSearchLinks:
    """Test search link generation."""

    def test_with_prospect_and_company(self, memory_db, mock_google):
        """Links generated for both prospect and company names."""
        engine = ResearchEngine(memory_db, google_client=mock_google)
        links = engine.build_search_links("John Doe", "Acme Corp")
        assert "Google: Person" in links
        assert "NMLS Lookup" in links
        assert "Google: Company" in links
        assert "Google: Company + Email" in links
        assert "Google: Person + Contact" in links

    def test_with_prospect_only(self, memory_db, mock_google):
        """Links generated for prospect name only (no company)."""
        engine = ResearchEngine(memory_db, google_client=mock_google)
        links = engine.build_search_links("John Doe", "")
        assert "Google: Person" in links
        assert "NMLS Lookup" in links
        assert "Google: Company" not in links
        assert "Google: Person + Contact" not in links

    def test_with_company_only(self, memory_db, mock_google):
        """Links generated for company name only (no prospect)."""
        engine = ResearchEngine(memory_db, google_client=mock_google)
        links = engine.build_search_links("", "Acme Corp")
        assert "Google: Company" in links
        assert "Google: Person" not in links

    def test_both_empty(self, memory_db, mock_google):
        """No links generated when both names are empty."""
        engine = ResearchEngine(memory_db, google_client=mock_google)
        links = engine.build_search_links("", "")
        assert len(links) == 0


# =============================================================================
# ResearchEngine.research_prospect
# =============================================================================


class TestResearchProspect:
    """Test full prospect research workflow."""

    def test_nonexistent_prospect(self, memory_db, mock_google):
        """Researching nonexistent prospect returns empty result."""
        engine = ResearchEngine(memory_db, google_client=mock_google)
        result = engine.research_prospect(999)
        assert result.prospect_id == 999
        assert result.findings == []
        assert result.auto_fill == []
        assert result.suggestions == []
        assert result.search_links == {}

    def test_broken_prospect_gets_email_suggestions(self, research_db, mock_google):
        """Broken prospect with domain gets email pattern suggestions."""
        db, company_id, prospect_id = research_db
        engine = ResearchEngine(db, google_client=mock_google)
        result = engine.research_prospect(prospect_id)

        assert result.prospect_id == prospect_id
        # Should generate MEDIUM confidence email candidates
        assert len(result.findings) > 0
        for finding in result.findings:
            assert finding.field == "email"
            assert finding.confidence == FindingConfidence.MEDIUM
            assert finding.source == "email_pattern"

        # All email findings go into suggestions (not auto_fill, since MEDIUM)
        assert len(result.auto_fill) == 0
        assert len(result.suggestions) > 0

    def test_search_links_include_company_website(self, research_db, mock_google):
        """Result search links include the company website."""
        db, company_id, prospect_id = research_db
        engine = ResearchEngine(db, google_client=mock_google)
        result = engine.research_prospect(prospect_id)
        assert "Company Website" in result.search_links
        assert "acmelending.com" in result.search_links["Company Website"]

    def test_creates_research_task(self, research_db, mock_google):
        """Research creates a research task record."""
        db, company_id, prospect_id = research_db
        engine = ResearchEngine(db, google_client=mock_google)
        engine.research_prospect(prospect_id)

        tasks = db.get_research_tasks()
        assert len(tasks) > 0
        assert any(t.prospect_id == prospect_id for t in tasks)

    def test_prospect_with_email_skips_pattern_detection(self, memory_db, mock_google):
        """Prospect with existing email does not get email pattern suggestions."""
        company = Company(name="Test Corp", domain="test.com", state="CA")
        cid = memory_db.create_company(company)
        prospect = Prospect(
            company_id=cid,
            first_name="Jane",
            last_name="Smith",
            population=Population.BROKEN,
        )
        pid = memory_db.create_prospect(prospect)
        # Add an email -- the prospect already has one
        memory_db.create_contact_method(
            ContactMethod(
                prospect_id=pid,
                type=ContactMethodType.EMAIL,
                value="jane@test.com",
            )
        )

        engine = ResearchEngine(memory_db, google_client=mock_google)
        result = engine.research_prospect(pid)
        email_findings = [f for f in result.findings if f.field == "email"]
        assert len(email_findings) == 0


# =============================================================================
# ResearchEngine.run_batch
# =============================================================================


class TestRunBatch:
    """Test batch research processing."""

    def test_batch_processes_broken_prospects(self, research_db, mock_google):
        """Batch processes broken prospects and returns count."""
        db, company_id, prospect_id = research_db
        engine = ResearchEngine(db, google_client=mock_google)
        count = engine.run_batch(limit=10)
        assert count == 1

    def test_batch_empty_database(self, memory_db, mock_google):
        """Batch with no broken prospects returns 0."""
        engine = ResearchEngine(memory_db, google_client=mock_google)
        count = engine.run_batch(limit=10)
        assert count == 0

    def test_batch_respects_limit(self, memory_db, mock_google):
        """Batch respects the limit parameter."""
        company = Company(name="Test Corp", domain="test.com", state="CA")
        cid = memory_db.create_company(company)
        # Create 5 broken prospects
        for i in range(5):
            p = Prospect(
                company_id=cid,
                first_name=f"Person{i}",
                last_name="Test",
                population=Population.BROKEN,
            )
            memory_db.create_prospect(p)

        engine = ResearchEngine(memory_db, google_client=mock_google)
        count = engine.run_batch(limit=3)
        assert count == 3


# =============================================================================
# ResearchEngine._apply_finding
# =============================================================================


class TestApplyFinding:
    """Test finding application logic."""

    def test_apply_high_confidence_email(self, research_db, mock_google):
        """HIGH confidence email finding is applied."""
        db, company_id, prospect_id = research_db
        engine = ResearchEngine(db, google_client=mock_google)

        finding = ResearchFinding(
            field="email",
            value="john.doe@acmelending.com",
            confidence=FindingConfidence.HIGH,
            source="google_search",
            source_url="https://example.com",
            context="Found on web",
        )
        result = engine._apply_finding(prospect_id, finding)
        assert result is True

        # Verify the contact method was created
        methods = db.get_contact_methods(prospect_id)
        emails = [m for m in methods if m.type == ContactMethodType.EMAIL]
        assert len(emails) == 1
        assert emails[0].value == "john.doe@acmelending.com"

        # Verify an enrichment activity was logged
        activities = db.get_activities(prospect_id)
        enrichments = [a for a in activities if a.activity_type == ActivityType.ENRICHMENT]
        assert len(enrichments) == 1

    def test_reject_medium_confidence(self, research_db, mock_google):
        """MEDIUM confidence finding is NOT applied."""
        db, company_id, prospect_id = research_db
        engine = ResearchEngine(db, google_client=mock_google)

        finding = ResearchFinding(
            field="email",
            value="john@acmelending.com",
            confidence=FindingConfidence.MEDIUM,
            source="email_pattern",
        )
        result = engine._apply_finding(prospect_id, finding)
        assert result is False

    def test_reject_low_confidence(self, research_db, mock_google):
        """LOW confidence finding is NOT applied."""
        db, company_id, prospect_id = research_db
        engine = ResearchEngine(db, google_client=mock_google)

        finding = ResearchFinding(
            field="email",
            value="john@acmelending.com",
            confidence=FindingConfidence.LOW,
            source="google_search",
        )
        result = engine._apply_finding(prospect_id, finding)
        assert result is False

    def test_apply_high_confidence_phone(self, research_db, mock_google):
        """HIGH confidence phone finding is applied."""
        db, company_id, prospect_id = research_db
        engine = ResearchEngine(db, google_client=mock_google)

        finding = ResearchFinding(
            field="phone",
            value="555-987-6543",
            confidence=FindingConfidence.HIGH,
            source="google_search",
        )
        # The prospect already has one phone; this is a different number
        result = engine._apply_finding(prospect_id, finding)
        assert result is True

    def test_duplicate_not_applied(self, research_db, mock_google):
        """Duplicate contact method is not re-added."""
        db, company_id, prospect_id = research_db
        engine = ResearchEngine(db, google_client=mock_google)

        # The prospect already has phone "555-123-4567"
        finding = ResearchFinding(
            field="phone",
            value="555-123-4567",
            confidence=FindingConfidence.HIGH,
            source="google_search",
        )
        result = engine._apply_finding(prospect_id, finding)
        assert result is False

    def test_unknown_field_not_applied(self, research_db, mock_google):
        """Unknown field type is not applied."""
        db, company_id, prospect_id = research_db
        engine = ResearchEngine(db, google_client=mock_google)

        finding = ResearchFinding(
            field="address",
            value="123 Main St",
            confidence=FindingConfidence.HIGH,
            source="google_search",
        )
        result = engine._apply_finding(prospect_id, finding)
        assert result is False


# =============================================================================
# ResearchEngine.scrape_company_site
# =============================================================================


class TestScrapeCompanySite:
    """Test company site scraping (deferred to manual)."""

    def test_returns_empty_list(self, memory_db, mock_google):
        """scrape_company_site returns empty list (scraping deferred)."""
        engine = ResearchEngine(memory_db, google_client=mock_google)
        findings = engine.scrape_company_site("acme.com")
        assert findings == []

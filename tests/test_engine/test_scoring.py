"""Tests for prospect scoring.

Tests Step 2.2: Scoring Algorithm
    - Score calculation 0-100
    - Engaged scores higher than unengaged
    - CEO scores higher than Associate
    - Confidence calculation
    - Complete vs sparse data differentiation
"""

from datetime import date, timedelta

import pytest

from src.db.models import (
    Company,
    ContactMethod,
    ContactMethodType,
    EngagementStage,
    Population,
    Prospect,
)
from src.engine.scoring import (
    DEFAULT_WEIGHTS,
    ScoreWeights,
    _score_company_fit,
    _score_contact_quality,
    _score_engagement,
    _score_source,
    _score_timing,
    calculate_confidence,
    calculate_score,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def full_company():
    """Company with complete data."""
    return Company(
        name="ABC Lending",
        state="TX",
        domain="abclending.com",
        loan_types='["bridge", "fix_and_flip"]',
        size="medium",
    )


@pytest.fixture
def sparse_company():
    """Company with minimal data."""
    return Company(name="Unknown Co")


@pytest.fixture
def ceo_prospect():
    """CEO-level prospect with strong data."""
    return Prospect(
        company_id=1,
        first_name="John",
        last_name="Smith",
        title="CEO",
        population=Population.ENGAGED,
        engagement_stage=EngagementStage.CLOSING,
        last_contact_date=date.today() - timedelta(days=3),
        follow_up_date=date.today(),
        source="Referral",
        notes="Interested in our product, evaluating vendors. Budget approved.",
    )


@pytest.fixture
def associate_prospect():
    """Associate-level prospect with weak data."""
    return Prospect(
        company_id=1,
        first_name="Alex",
        last_name="Intern",
        title="Associate",
        population=Population.BROKEN,
        source="Purchased List",
    )


@pytest.fixture
def unengaged_prospect():
    """Standard unengaged prospect."""
    return Prospect(
        company_id=1,
        first_name="Jane",
        last_name="Doe",
        title="VP of Operations",
        population=Population.UNENGAGED,
        last_contact_date=date.today() - timedelta(days=10),
        source="Conference",
    )


# =============================================================================
# SCORE WEIGHTS
# =============================================================================


class TestScoreWeights:
    """Test score weight configuration."""

    def test_default_weights(self):
        """Default weights are defined."""
        weights = ScoreWeights()
        assert weights.company_fit > 0
        assert weights.engagement_signals > 0

    def test_default_weights_sum_to_100(self):
        """Default weights total 100."""
        w = DEFAULT_WEIGHTS
        total = (
            w.company_fit
            + w.contact_quality
            + w.engagement_signals
            + w.timing_signals
            + w.source_quality
        )
        assert total == 100


# =============================================================================
# CALCULATE SCORE
# =============================================================================


class TestCalculateScore:
    """Test composite score calculation."""

    def test_score_range(self, ceo_prospect, full_company):
        """Score is in valid range 0-100."""
        score = calculate_score(ceo_prospect, full_company)
        assert 0 <= score <= 100

    def test_engaged_scores_higher_than_unengaged(
        self, ceo_prospect, unengaged_prospect, full_company
    ):
        """Engaged prospects score meaningfully higher than unengaged."""
        engaged_score = calculate_score(ceo_prospect, full_company)
        unengaged_score = calculate_score(unengaged_prospect, full_company)
        assert engaged_score > unengaged_score
        # Should be at least 10 points apart to be meaningful
        assert engaged_score - unengaged_score >= 10

    def test_full_data_scores_higher(self, unengaged_prospect, full_company, sparse_company):
        """Full company data scores meaningfully higher than sparse."""
        full_score = calculate_score(unengaged_prospect, full_company)
        sparse_score = calculate_score(unengaged_prospect, sparse_company)
        assert full_score > sparse_score
        # Company fit is 25% of score; full=100 vs sparse=30 -> ~17pt difference
        assert full_score - sparse_score >= 10

    def test_broken_scores_low(self, associate_prospect, sparse_company):
        """Broken prospect with sparse data scores below 40."""
        score = calculate_score(associate_prospect, sparse_company)
        assert score < 40

    def test_dnc_prospect_scores_near_zero(self, sparse_company):
        """DNC prospect engagement is 0, dragging total score very low."""
        dnc = Prospect(
            company_id=1,
            first_name="Dead",
            last_name="Contact",
            population=Population.DEAD_DNC,
        )
        score = calculate_score(dnc, sparse_company)
        # Engagement=0 (25% weight) plus weak everything else
        assert score < 30

    def test_custom_weights(self, unengaged_prospect, full_company):
        """Custom weights produce different scores."""
        heavy_engagement = ScoreWeights(
            company_fit=5,
            contact_quality=5,
            engagement_signals=80,
            timing_signals=5,
            source_quality=5,
        )
        default_score = calculate_score(unengaged_prospect, full_company)
        custom_score = calculate_score(unengaged_prospect, full_company, weights=heavy_engagement)
        # Scores differ because weights differ
        assert default_score != custom_score


# =============================================================================
# INDIVIDUAL SCORE COMPONENTS
# =============================================================================


class TestCompanyFit:
    """Test company fit scoring."""

    def test_full_company_exact_score(self, full_company):
        """Company with loan_types + size=medium + state=TX = capped at 100."""
        # loan_types: 40, size medium: 70, state: 30 = 140 -> capped to 100
        score = _score_company_fit(full_company)
        assert score == 100

    def test_sparse_company_exact_score(self, sparse_company):
        """Company with only name gets baseline scores."""
        # no loan_types: 15, no size: 15, no state/domain: 0 = 30
        score = _score_company_fit(sparse_company)
        assert score == 30

    def test_company_with_domain_only(self):
        """Company with domain but no state gets partial geography credit."""
        company = Company(name="DomainCo", domain="domainco.com")
        # no loan_types: 15, no size: 15, domain: 15 = 45
        score = _score_company_fit(company)
        assert score == 45


class TestContactQuality:
    """Test contact quality scoring."""

    def test_ceo_exact_score(self, ceo_prospect, full_company):
        """CEO with full data: seniority=100 -> 60*100/100=60, completeness=35."""
        # title=60*(100/100)=60, first+last+title+domain+state = 10+10+10+5+5=40
        # Total = 100 (capped)
        ceo_score = _score_contact_quality(ceo_prospect, full_company)
        assert ceo_score == 100

    def test_associate_exact_score(self, associate_prospect, full_company):
        """Associate with partial data scores distinctly lower than CEO."""
        # title "Associate" -> seniority=20 -> 60*20/100=12
        # first+last+title+domain+state = 10+10+10+5+5=40
        # Total = 52
        associate_score = _score_contact_quality(associate_prospect, full_company)
        assert associate_score == 52

    def test_ceo_scores_higher_than_associate(self, ceo_prospect, associate_prospect, full_company):
        """CEO title scores higher than Associate (at least 30 points gap)."""
        ceo_score = _score_contact_quality(ceo_prospect, full_company)
        associate_score = _score_contact_quality(associate_prospect, full_company)
        assert ceo_score > associate_score
        assert ceo_score - associate_score >= 30

    def test_no_title_exact_score(self, full_company):
        """No title produces specific low score."""
        prospect = Prospect(company_id=1, first_name="Unknown", last_name="Person")
        # no title: 10, first+last=20, no title field=0, domain+state=10 = 40
        score = _score_contact_quality(prospect, full_company)
        assert score == 40


class TestEngagement:
    """Test engagement signal scoring."""

    def test_engaged_closing_highest(self):
        """Engaged at closing stage scores highest."""
        prospect = Prospect(
            company_id=1,
            first_name="A",
            last_name="B",
            population=Population.ENGAGED,
            engagement_stage=EngagementStage.CLOSING,
        )
        score = _score_engagement(prospect)
        assert score == 100

    def test_broken_scores_lowest(self):
        """Broken population scores lowest non-DNC."""
        prospect = Prospect(
            company_id=1,
            first_name="A",
            last_name="B",
            population=Population.BROKEN,
        )
        score = _score_engagement(prospect)
        assert score == 10

    def test_dnc_scores_zero(self):
        """DNC population scores zero."""
        prospect = Prospect(
            company_id=1,
            first_name="A",
            last_name="B",
            population=Population.DEAD_DNC,
        )
        score = _score_engagement(prospect)
        assert score == 0


class TestTiming:
    """Test timing signal scoring."""

    def test_recent_contact_scores_high(self):
        """Contact within 7 days scores high."""
        prospect = Prospect(
            company_id=1,
            first_name="A",
            last_name="B",
            last_contact_date=date.today() - timedelta(days=2),
        )
        score = _score_timing(prospect)
        assert score >= 70

    def test_no_contact_gets_baseline(self):
        """No contact history gets baseline score."""
        prospect = Prospect(company_id=1, first_name="A", last_name="B")
        score = _score_timing(prospect)
        assert score == 30


class TestSource:
    """Test source quality scoring."""

    def test_referral_scores_highest(self):
        """Referral source scores highest."""
        prospect = Prospect(company_id=1, first_name="A", last_name="B", source="Referral")
        score = _score_source(prospect)
        assert score == 100

    def test_cold_scores_lowest(self):
        """Cold source scores lowest."""
        prospect = Prospect(company_id=1, first_name="A", last_name="B", source="Cold")
        score = _score_source(prospect)
        assert score == 20

    def test_no_source_gets_default(self):
        """No source gets default score."""
        prospect = Prospect(company_id=1, first_name="A", last_name="B")
        score = _score_source(prospect)
        assert score == 30


# =============================================================================
# CONFIDENCE
# =============================================================================


class TestCalculateConfidence:
    """Test confidence calculation."""

    def test_confidence_range(self, ceo_prospect):
        """Confidence is in valid range 0-100."""
        methods = [
            ContactMethod(
                prospect_id=1,
                type=ContactMethodType.EMAIL,
                value="john@test.com",
                is_verified=True,
                verified_date=date.today(),
            ),
            ContactMethod(
                prospect_id=1,
                type=ContactMethodType.PHONE,
                value="5551234567",
                is_verified=True,
                verified_date=date.today(),
            ),
        ]
        confidence = calculate_confidence(ceo_prospect, methods)
        assert 0 <= confidence <= 100

    def test_complete_data_high_confidence(self, ceo_prospect):
        """Complete verified data produces high confidence."""
        methods = [
            ContactMethod(
                prospect_id=1,
                type=ContactMethodType.EMAIL,
                value="john@test.com",
                is_verified=True,
                verified_date=date.today(),
            ),
            ContactMethod(
                prospect_id=1,
                type=ContactMethodType.PHONE,
                value="5551234567",
                is_verified=True,
                verified_date=date.today(),
            ),
        ]
        confidence = calculate_confidence(ceo_prospect, methods)
        assert confidence >= 70

    def test_missing_data_low_confidence(self):
        """Missing data reduces confidence."""
        prospect = Prospect(company_id=1, first_name="Unknown", last_name="")
        confidence = calculate_confidence(prospect, [])
        assert confidence < 50

    def test_both_methods_better_than_one(self, unengaged_prospect):
        """Having both email and phone is better than just one."""
        email_only = [
            ContactMethod(
                prospect_id=1,
                type=ContactMethodType.EMAIL,
                value="jane@test.com",
            ),
        ]
        both = [
            ContactMethod(
                prospect_id=1,
                type=ContactMethodType.EMAIL,
                value="jane@test.com",
            ),
            ContactMethod(
                prospect_id=1,
                type=ContactMethodType.PHONE,
                value="5551234567",
            ),
        ]
        email_conf = calculate_confidence(unengaged_prospect, email_only)
        both_conf = calculate_confidence(unengaged_prospect, both)
        assert both_conf > email_conf

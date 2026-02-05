"""Prospect scoring algorithm.

Calculates 0-100 composite score from weighted categories:
    - Company fit (loan types, size, geography)
    - Contact quality (title, data completeness)
    - Engagement signals (responses, demo interest)
    - Timing signals (budget cycle, recent contact)
    - Source quality (where they came from)

Weights are manually tuned based on Jeff's sales intuition.
No auto-tuning until 12+ months of data.

Usage:
    from src.engine.scoring import calculate_score, calculate_confidence

    score = calculate_score(prospect, company)
    confidence = calculate_confidence(prospect, contact_methods)
"""

from dataclasses import dataclass
from typing import Optional

from src.core.logging import get_logger
from src.db.models import (
    Company,
    ContactMethod,
    EngagementStage,
    Population,
    Prospect,
)

logger = get_logger(__name__)


# =============================================================================
# SCORING WEIGHTS (manually tuned)
# =============================================================================


@dataclass
class ScoreWeights:
    """Scoring category weights.

    Total should equal 100.
    """

    company_fit: int = 25
    contact_quality: int = 20
    engagement_signals: int = 25
    timing_signals: int = 15
    source_quality: int = 15


DEFAULT_WEIGHTS = ScoreWeights()


# =============================================================================
# SCORING FUNCTIONS
# =============================================================================


def calculate_score(
    prospect: Prospect,
    company: Company,
    weights: ScoreWeights = DEFAULT_WEIGHTS,
) -> int:
    """Calculate prospect score 0-100.

    Args:
        prospect: Prospect record
        company: Company record
        weights: Score weights to use

    Returns:
        Score from 0 to 100
    """
    raise NotImplementedError("Phase 2, Step 2.2")


def calculate_confidence(
    prospect: Prospect,
    contact_methods: list[ContactMethod],
) -> int:
    """Calculate data confidence score 0-100.

    Based on:
        - Field completeness
        - Verification status
        - Verification freshness
        - Source reliability

    Args:
        prospect: Prospect record
        contact_methods: Prospect's contact methods

    Returns:
        Confidence from 0 to 100
    """
    raise NotImplementedError("Phase 2, Step 2.2")


def _score_company_fit(company: Company) -> int:
    """Score company fit 0-100.

    Factors:
        - Loan types match target market
        - Company size is appropriate
        - Geography is serviceable
    """
    raise NotImplementedError("Phase 2, Step 2.2")


def _score_contact_quality(prospect: Prospect, company: Company) -> int:
    """Score contact quality 0-100.

    Factors:
        - Title seniority (CEO > VP > Manager > Associate)
        - Data completeness
        - Verification status
    """
    raise NotImplementedError("Phase 2, Step 2.2")


def _score_engagement(prospect: Prospect) -> int:
    """Score engagement signals 0-100.

    Factors:
        - Current population (engaged > unengaged > broken)
        - Engagement stage (closing > post-demo > demo-scheduled)
        - Response history
    """
    raise NotImplementedError("Phase 2, Step 2.2")


def _score_timing(prospect: Prospect) -> int:
    """Score timing signals 0-100.

    Factors:
        - Recent contact (warmer is better)
        - Budget cycle indicators
        - Decision timeline from intel
    """
    raise NotImplementedError("Phase 2, Step 2.2")


def _score_source(prospect: Prospect) -> int:
    """Score source quality 0-100.

    Factors:
        - Referral > Inbound > Conference > List
        - Source reliability history
    """
    raise NotImplementedError("Phase 2, Step 2.2")


def rescore_all(db) -> int:
    """Re-score all active prospects.

    Called during nightly cycle.

    Returns:
        Number of prospects re-scored
    """
    raise NotImplementedError("Phase 5, Step 5.8")

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
from datetime import date, timedelta
from typing import Optional

from src.core.logging import get_logger
from src.db.models import (
    Company,
    ContactMethod,
    ContactMethodType,
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

# Title seniority lookup (higher = more senior = better contact)
TITLE_SENIORITY: dict[str, int] = {
    "ceo": 100,
    "chief executive officer": 100,
    "president": 95,
    "owner": 95,
    "founder": 90,
    "co-founder": 88,
    "coo": 85,
    "chief operating officer": 85,
    "cto": 85,
    "chief technology officer": 85,
    "cfo": 80,
    "chief financial officer": 80,
    "evp": 78,
    "executive vice president": 78,
    "svp": 75,
    "senior vice president": 75,
    "vp": 70,
    "vice president": 70,
    "director": 60,
    "senior manager": 50,
    "manager": 40,
    "supervisor": 30,
    "associate": 20,
    "analyst": 15,
    "coordinator": 10,
}

# Source quality rankings
SOURCE_QUALITY: dict[str, int] = {
    "referral": 100,
    "inbound": 85,
    "warm intro": 80,
    "conference": 70,
    "webinar": 65,
    "phoneburner": 50,
    "linkedin": 45,
    "list": 40,
    "purchased list": 30,
    "cold": 20,
}

# Company size scoring
SIZE_SCORES: dict[str, int] = {
    "enterprise": 90,
    "large": 80,
    "medium": 70,
    "small": 50,
}


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
    company_fit = _score_company_fit(company)
    contact_quality = _score_contact_quality(prospect, company)
    engagement = _score_engagement(prospect)
    timing = _score_timing(prospect)
    source = _score_source(prospect)

    # Weighted composite (each sub-score is 0-100, weight is percentage)
    raw = (
        company_fit * weights.company_fit
        + contact_quality * weights.contact_quality
        + engagement * weights.engagement_signals
        + timing * weights.timing_signals
        + source * weights.source_quality
    ) / 100

    # Clamp to 0-100
    return max(0, min(100, int(round(raw))))


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
    score = 0
    max_score = 0

    # Name completeness (10 points)
    max_score += 10
    if prospect.first_name and prospect.last_name:
        score += 10
    elif prospect.first_name or prospect.last_name:
        score += 5

    # Title (10 points)
    max_score += 10
    if prospect.title:
        score += 10

    # Company (5 points - implied by company_id existing)
    max_score += 5
    if prospect.company_id:
        score += 5

    # Contact methods (30 points total)
    has_email = False
    has_phone = False
    verified_count = 0

    for method in contact_methods:
        if method.type == ContactMethodType.EMAIL:
            has_email = True
        elif method.type == ContactMethodType.PHONE:
            has_phone = True
        if method.is_verified:
            verified_count += 1

    max_score += 30
    if has_email:
        score += 10
    if has_phone:
        score += 10
    if has_email and has_phone:
        score += 5  # Bonus for both
    if verified_count > 0:
        score += 5

    # Verification freshness (15 points)
    max_score += 15
    fresh_verified = any(
        m.is_verified
        and m.verified_date
        and (isinstance(m.verified_date, str) or (date.today() - m.verified_date).days < 90)
        for m in contact_methods
    )
    if fresh_verified:
        score += 15
    elif verified_count > 0:
        score += 8  # Verified but possibly stale

    # Source reliability (15 points)
    max_score += 15
    if prospect.source:
        source_lower = prospect.source.lower()
        for key, val in SOURCE_QUALITY.items():
            if key in source_lower:
                score += int(15 * val / 100)
                break
        else:
            score += 7  # Unknown source gets middle score
    else:
        score += 3  # No source info

    # Notes / intel (15 points)
    max_score += 15
    if prospect.notes and len(prospect.notes) > 20:
        score += 15
    elif prospect.notes:
        score += 8

    if max_score == 0:
        return 0

    return max(0, min(100, int(round(score * 100 / max_score))))


def _score_company_fit(company: Company) -> int:
    """Score company fit 0-100.

    Factors:
        - Loan types match target market
        - Company size is appropriate
        - Geography is serviceable
    """
    score = 0

    # Loan types (40 points) - having loan_types data is a signal
    if company.loan_types:
        score += 40
    else:
        score += 15  # Unknown loan types, could be anything

    # Company size (30 points)
    if company.size:
        score += SIZE_SCORES.get(company.size.lower(), 50)  # Default to medium
    else:
        score += 15  # Unknown size

    # Geography (30 points) - having a state means we know the market
    if company.state:
        score += 30
    elif company.domain:
        score += 15  # Domain suggests some known presence

    return min(100, score)


def _score_contact_quality(prospect: Prospect, company: Company) -> int:
    """Score contact quality 0-100.

    Factors:
        - Title seniority (CEO > VP > Manager > Associate)
        - Data completeness
        - Verification status
    """
    score = 0

    # Title seniority (60 points)
    if prospect.title:
        title_lower = prospect.title.lower().strip()
        best_match = 20  # Default for unknown titles
        for title_key, seniority in TITLE_SENIORITY.items():
            if title_key in title_lower:
                best_match = max(best_match, seniority)
        score += int(60 * best_match / 100)
    else:
        score += 10  # No title

    # Data completeness (40 points)
    completeness = 0
    if prospect.first_name:
        completeness += 10
    if prospect.last_name:
        completeness += 10
    if prospect.title:
        completeness += 10
    if company.domain:
        completeness += 5
    if company.state:
        completeness += 5
    score += completeness

    return min(100, score)


def _score_engagement(prospect: Prospect) -> int:
    """Score engagement signals 0-100.

    Factors:
        - Current population (engaged > unengaged > broken)
        - Engagement stage (closing > post-demo > demo-scheduled)
        - Response history
    """
    # Population-based baseline
    pop_scores = {
        Population.ENGAGED: 70,
        Population.UNENGAGED: 40,
        Population.BROKEN: 10,
        Population.PARKED: 30,
        Population.LOST: 5,
        Population.DEAD_DNC: 0,
        Population.PARTNERSHIP: 20,
        Population.CLOSED_WON: 100,
    }
    score = pop_scores.get(prospect.population, 20)

    # Engagement stage bonus (within ENGAGED)
    if prospect.population == Population.ENGAGED and prospect.engagement_stage:
        stage_bonus = {
            EngagementStage.PRE_DEMO: 0,
            EngagementStage.DEMO_SCHEDULED: 10,
            EngagementStage.POST_DEMO: 20,
            EngagementStage.CLOSING: 30,
        }
        score += stage_bonus.get(prospect.engagement_stage, 0)

    return min(100, score)


def _score_timing(prospect: Prospect) -> int:
    """Score timing signals 0-100.

    Factors:
        - Recent contact (warmer is better)
        - Budget cycle indicators
        - Decision timeline from intel
    """
    score = 30  # Baseline

    # Recency of last contact
    if prospect.last_contact_date:
        if isinstance(prospect.last_contact_date, str):
            # Handle string dates
            score += 30
        else:
            days_since = (date.today() - prospect.last_contact_date).days
            if days_since <= 7:
                score += 50  # Hot - contacted this week
            elif days_since <= 14:
                score += 40  # Warm - contacted in last 2 weeks
            elif days_since <= 30:
                score += 30  # Cooling
            elif days_since <= 60:
                score += 15  # Getting cold
            elif days_since <= 90:
                score += 5  # Cold
            # > 90 days: no bonus

    # Follow-up date proximity bonus
    if prospect.follow_up_date:
        score += 10  # Having a follow-up set is a positive signal

    return min(100, score)


def _score_source(prospect: Prospect) -> int:
    """Score source quality 0-100.

    Factors:
        - Referral > Inbound > Conference > List
        - Source reliability history
    """
    if not prospect.source:
        return 30  # Unknown source gets a default

    source_lower = prospect.source.lower()
    for key, val in SOURCE_QUALITY.items():
        if key in source_lower:
            return val

    return 40  # Unrecognized source


def rescore_all(db) -> int:
    """Re-score all active prospects.

    Called during nightly cycle.

    Iterates all prospects in active populations (UNENGAGED, ENGAGED, BROKEN),
    recalculates their prospect_score and data_confidence, and persists updates.

    Returns:
        Number of prospects re-scored
    """
    active_populations = [
        Population.UNENGAGED,
        Population.ENGAGED,
        Population.BROKEN,
    ]

    count = 0

    for pop in active_populations:
        prospects = db.get_prospects(population=pop, limit=10000)

        for prospect in prospects:
            # Fetch related data
            company = db.get_company(prospect.company_id) if prospect.company_id else None
            contact_methods = db.get_contact_methods(prospect.id)

            if company is None:
                # Create a minimal Company so scoring doesn't break
                company = Company()

            # Calculate new scores
            new_score = calculate_score(prospect, company)
            new_confidence = calculate_confidence(prospect, contact_methods)

            # Update if changed
            if prospect.prospect_score != new_score or prospect.data_confidence != new_confidence:
                prospect.prospect_score = new_score
                prospect.data_confidence = new_confidence
                db.update_prospect(prospect)

            count += 1

    logger.info(
        "Rescore complete",
        extra={"context": {"rescored": count}},
    )
    return count

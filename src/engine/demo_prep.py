"""Demo preparation document generation.

Auto-generates demo prep from prospect data and notes:
    - Loan types
    - Company size
    - State/region
    - Pain points from notes
    - Competitive landscape from intel nuggets

Usage:
    from src.engine.demo_prep import generate_prep

    prep = generate_prep(db, prospect_id)
"""

from dataclasses import dataclass
from typing import Optional

from src.db.database import Database
from src.db.models import Prospect, Company, IntelNugget
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DemoPrep:
    """Demo preparation document.

    Attributes:
        prospect_name: Prospect name
        company_name: Company name
        loan_types: Loan types they handle
        company_size: Company size
        state: State/region
        pain_points: Known pain points
        competitors: Competitors they're evaluating
        decision_timeline: Known timeline
        key_facts: Other relevant facts
        talking_points: Suggested talking points
        questions_to_ask: Questions to explore
        history_summary: Summary of interaction history
    """

    prospect_name: str
    company_name: str
    loan_types: list[str]
    company_size: Optional[str] = None
    state: Optional[str] = None
    pain_points: Optional[list[str]] = None
    competitors: Optional[list[str]] = None
    decision_timeline: Optional[str] = None
    key_facts: Optional[list[str]] = None
    talking_points: Optional[list[str]] = None
    questions_to_ask: Optional[list[str]] = None
    history_summary: Optional[str] = None


def generate_prep(db: Database, prospect_id: int) -> DemoPrep:
    """Generate demo preparation document.

    Pulls data from prospect, company, activities, and intel nuggets.

    Args:
        db: Database instance
        prospect_id: Prospect ID

    Returns:
        DemoPrep document
    """
    raise NotImplementedError("Phase 3, Step 3.8")


def _extract_pain_points(nuggets: list[IntelNugget]) -> list[str]:
    """Extract pain points from intel nuggets."""
    raise NotImplementedError("Phase 3, Step 3.8")


def _extract_competitors(nuggets: list[IntelNugget]) -> list[str]:
    """Extract competitor mentions from intel nuggets."""
    raise NotImplementedError("Phase 3, Step 3.8")


def _generate_talking_points(prep: DemoPrep) -> list[str]:
    """Generate talking points based on prep data."""
    raise NotImplementedError("Phase 3, Step 3.8")


def _summarize_history(activities: list) -> str:
    """Summarize interaction history."""
    raise NotImplementedError("Phase 3, Step 3.8")

"""Learning engine - Qualitative patterns from notes.

Reads notes on won and lost deals to identify patterns:
    - "Lost to LoanPro because of price"
    - "Closed because they loved the borrower portal"
    - "Three losses mentioned pricing"

This is note-driven intelligence, not statistical modeling.
Works from day one with even a handful of closed deals.

Usage:
    from src.engine.learning import LearningEngine

    engine = LearningEngine(db)
    insights = engine.analyze_outcomes()
    suggestions = engine.get_suggestions_for_prospect(prospect_id)
"""

from collections import Counter
from dataclasses import dataclass
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database

logger = get_logger(__name__)


@dataclass
class WinPattern:
    """Pattern from won deals.

    Attributes:
        pattern: Description of pattern
        count: How many deals showed this
        examples: Example deal notes
    """

    pattern: str
    count: int
    examples: list[str]


@dataclass
class LossPattern:
    """Pattern from lost deals.

    Attributes:
        pattern: Description of pattern
        count: How many deals showed this
        competitor: Competitor if mentioned
        examples: Example deal notes
    """

    pattern: str
    count: int
    competitor: Optional[str] = None
    examples: Optional[list[str]] = None


@dataclass
class LearningInsights:
    """Insights from outcome analysis.

    Attributes:
        win_patterns: Patterns from won deals
        loss_patterns: Patterns from lost deals
        top_competitors: Most common competitors
        win_rate: Overall win rate
        avg_cycle_days: Average days to close
    """

    win_patterns: list[WinPattern]
    loss_patterns: list[LossPattern]
    top_competitors: list[tuple[str, int]]  # (name, count)
    win_rate: Optional[float] = None
    avg_cycle_days: Optional[float] = None


class LearningEngine:
    """Note-based qualitative learning.

    Analyzes notes on closed and lost deals to find patterns.
    """

    def __init__(self, db: Database):
        """Initialize learning engine.

        Args:
            db: Database instance
        """
        self.db = db

    def analyze_outcomes(self) -> LearningInsights:
        """Analyze all won and lost deals for patterns.

        Returns:
            LearningInsights with patterns found
        """
        raise NotImplementedError("Phase 7, Step 7.5")

    def get_suggestions_for_prospect(self, prospect_id: int) -> list[str]:
        """Get suggestions based on similar past deals.

        Args:
            prospect_id: Prospect to get suggestions for

        Returns:
            List of suggestions based on patterns
        """
        raise NotImplementedError("Phase 7, Step 7.5")

    def _extract_win_patterns(self, notes: list[str]) -> list[WinPattern]:
        """Extract patterns from winning deal notes."""
        raise NotImplementedError("Phase 7, Step 7.5")

    def _extract_loss_patterns(self, notes: list[str]) -> list[LossPattern]:
        """Extract patterns from lost deal notes."""
        raise NotImplementedError("Phase 7, Step 7.5")

    def _find_competitor_mentions(self, notes: list[str]) -> Counter:
        """Find competitor mentions in notes."""
        raise NotImplementedError("Phase 7, Step 7.5")

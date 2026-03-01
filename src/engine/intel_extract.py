"""Real-time intel nugget extraction.

Extracts intel from activity notes during card processing,
not just during the nightly cycle.

Usage:
    from src.engine.intel_extract import extract_intel_from_notes
    count = extract_intel_from_notes(db, prospect_id, notes)
"""

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import IntelCategory, IntelNugget

logger = get_logger(__name__)

# Keyword maps for each intel category
_PAIN_KEYWORDS = [
    "struggling with",
    "frustrated",
    "problem with",
    "challenge",
    "pain point",
    "issue with",
    "concerned about",
    "worried about",
    "bottleneck",
    "slow process",
    "manual process",
]

_COMPETITOR_KEYWORDS = [
    "competitor",
    "also looking at",
    "comparing",
    "currently using",
    "switched from",
    "considering",
    "vendor",
    "alternative",
]

_TIMELINE_KEYWORDS = [
    "by end of",
    "q1",
    "q2",
    "q3",
    "q4",
    "this quarter",
    "next month",
    "next quarter",
    "deadline",
    "timeline",
    "budget cycle",
    "fiscal year",
]

_BUDGET_KEYWORDS = [
    "budget",
    "funding",
    "approved for",
    "allocated",
    "cost",
    "pricing",
    "investment",
]

_DECISION_KEYWORDS = [
    "decision maker",
    "need to run it by",
    "board approval",
    "committee",
    "my boss",
    "ceo wants",
    "sign off",
]


def extract_intel_from_notes(
    db: Database,
    prospect_id: int,
    notes: str,
    source: str = "card_processing",
) -> int:
    """Extract intel nuggets from activity notes in real-time.

    Args:
        db: Database instance
        prospect_id: Prospect the notes are about
        notes: The activity notes / dictation text
        source: Where the extraction happened

    Returns:
        Number of new nuggets created
    """
    if not notes or not notes.strip():
        return 0

    notes_lower = notes.lower()
    nuggets_to_create: list[tuple[IntelCategory, str]] = []

    # Pain points
    for kw in _PAIN_KEYWORDS:
        if kw in notes_lower:
            nuggets_to_create.append(
                (IntelCategory.PAIN_POINT, f"Mentioned '{kw}': {notes[:200]}")
            )
            break

    # Competitors
    for kw in _COMPETITOR_KEYWORDS:
        if kw in notes_lower:
            nuggets_to_create.append(
                (IntelCategory.COMPETITOR, f"Competitor intel: {notes[:200]}")
            )
            break

    # Timeline
    for kw in _TIMELINE_KEYWORDS:
        if kw in notes_lower:
            nuggets_to_create.append(
                (IntelCategory.DECISION_TIMELINE, f"Timeline: {notes[:200]}")
            )
            break

    # Budget signals (mapped to KEY_FACT — closest available category)
    for kw in _BUDGET_KEYWORDS:
        if kw in notes_lower:
            nuggets_to_create.append(
                (IntelCategory.KEY_FACT, f"Budget signal: {notes[:200]}")
            )
            break

    # Decision process (mapped to DECISION_TIMELINE — closest available category)
    for kw in _DECISION_KEYWORDS:
        if kw in notes_lower:
            nuggets_to_create.append(
                (IntelCategory.DECISION_TIMELINE, f"Decision process: {notes[:200]}")
            )
            break

    # Deduplicate against existing nuggets
    created = 0
    existing = db.get_intel_nuggets(prospect_id)

    for category, content in nuggets_to_create:
        is_duplicate = any(
            n.category == category and n.content == content for n in existing
        )
        if not is_duplicate:
            nugget = IntelNugget(
                prospect_id=prospect_id,
                category=category,
                content=content,
            )
            try:
                db.create_intel_nugget(nugget)
                created += 1
                logger.info(
                    f"Intel nugget extracted in real-time",
                    extra={
                        "context": {
                            "prospect_id": prospect_id,
                            "category": category.value,
                            "source": source,
                        }
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to create intel nugget: {e}")

    return created

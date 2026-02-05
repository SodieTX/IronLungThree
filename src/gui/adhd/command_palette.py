"""Command palette - Quick fuzzy search with Ctrl+K.

Fuzzy search across tabs, prospects, actions, and settings.
Recent commands float to top. Keyboard navigation.

This module provides the search logic. The GUI overlay
(tkinter Toplevel) is wired in the app module.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PaletteItem:
    """An item searchable via the command palette."""

    label: str
    category: str  # "tab", "prospect", "action", "setting"
    action: Callable[[], None]
    keywords: list[str] = field(default_factory=list)


@dataclass
class PaletteResult:
    """A search result with relevance score."""

    item: PaletteItem
    score: float  # Higher is better


class CommandPalette:
    """Searchable command index with fuzzy matching.

    Items are registered by category. Search returns scored results
    with recently-used items boosted.
    """

    def __init__(self) -> None:
        self._items: list[PaletteItem] = []
        self._recent: list[str] = []  # labels of recently executed items
        self._max_recent: int = 10

    def register(self, item: PaletteItem) -> None:
        """Register a searchable item."""
        self._items.append(item)

    def register_many(self, items: list[PaletteItem]) -> None:
        """Register multiple items at once."""
        self._items.extend(items)

    def clear(self) -> None:
        """Clear all registered items."""
        self._items.clear()

    def item_count(self) -> int:
        """Number of registered items."""
        return len(self._items)

    def search(self, query: str, limit: int = 20) -> list[PaletteResult]:
        """Search items by fuzzy match.

        Scoring:
        - Exact prefix match in label: high score
        - Substring match in label: medium-high score
        - Fuzzy match in label: medium score
        - Substring match in keywords: medium score
        - Fuzzy match in keywords: low score
        - Recent usage: boost

        Returns results sorted by score descending.
        """
        if not query.strip():
            # No query: return recent items first, then all by category
            return self._all_items_ranked(limit)

        query_lower = query.lower().strip()
        results: list[PaletteResult] = []

        for item in self._items:
            score = self._score_item(item, query_lower)
            if score > 0:
                results.append(PaletteResult(item=item, score=score))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def execute(self, result: PaletteResult) -> None:
        """Execute a palette result and track it as recent."""
        label = result.item.label
        # Update recent list
        if label in self._recent:
            self._recent.remove(label)
        self._recent.insert(0, label)
        if len(self._recent) > self._max_recent:
            self._recent = self._recent[: self._max_recent]

        logger.debug(
            "Palette command executed",
            extra={"context": {"label": label, "category": result.item.category}},
        )
        result.item.action()

    def get_recent(self) -> list[str]:
        """Get recently executed command labels."""
        return list(self._recent)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_item(self, item: PaletteItem, query: str) -> float:
        """Score an item against a query. 0 means no match."""
        score = 0.0
        label_lower = item.label.lower()

        # Exact prefix match — best
        if label_lower.startswith(query):
            score += 100.0
        # Substring match in label
        elif query in label_lower:
            score += 60.0
        # Fuzzy: all query chars in order in label
        elif self._fuzzy_match(query, label_lower):
            score += 30.0
        else:
            # Check keywords
            for kw in item.keywords:
                if query in kw.lower():
                    score += 40.0
                    break
                elif self._fuzzy_match(query, kw.lower()):
                    score += 15.0
                    break

        if score == 0:
            return 0

        # Recency boost
        if item.label in self._recent:
            idx = self._recent.index(item.label)
            score += max(0, 20 - idx * 2)

        return score

    @staticmethod
    def _fuzzy_match(query: str, target: str) -> bool:
        """Check if all characters of query appear in order in target."""
        it = iter(target)
        return all(c in it for c in query)

    def _all_items_ranked(self, limit: int) -> list[PaletteResult]:
        """Return all items with recent ones first."""
        recent_set = set(self._recent)
        results: list[PaletteResult] = []
        for item in self._items:
            score = 50.0 if item.label in recent_set else 1.0
            if item.label in self._recent:
                score += max(0, 20 - self._recent.index(item.label) * 2)
            results.append(PaletteResult(item=item, score=score))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

"""Google Custom Search integration for autonomous research.

Free tier: 100 queries per day.
Used sparingly for finding missing contact information.

Usage:
    from src.integrations.google_search import GoogleSearchClient

    client = GoogleSearchClient()
    results = client.search("John Smith ABC Lending contact")
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

from src.core.logging import get_logger
from src.integrations.base import IntegrationBase

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """Google search result.

    Attributes:
        title: Result title
        url: Result URL
        snippet: Result snippet
    """

    title: str
    url: str
    snippet: str


class GoogleSearchClient(IntegrationBase):
    """Google Custom Search API client.

    Free tier limits:
        - 100 queries per day
        - Results cached to minimize API calls
    """

    def __init__(self, api_key: Optional[str] = None, cx: Optional[str] = None):
        """Initialize Google Search client.

        Args:
            api_key: Google API key (optional, uses env var if not provided)
            cx: Custom Search Engine ID
        """
        self._api_key = api_key
        self._cx = cx
        self._queries_today = 0
        self._query_date: Optional[date] = None

    def health_check(self) -> bool:
        """Check if Google Search API is reachable."""
        raise NotImplementedError("Phase 5, Step 5.1")

    def is_configured(self) -> bool:
        """Check if Google Search is configured."""
        return bool(self._api_key and self._cx)

    def search(
        self,
        query: str,
        num_results: int = 10,
    ) -> list[SearchResult]:
        """Execute Google search.

        Args:
            query: Search query
            num_results: Maximum results (max 10 per API call)

        Returns:
            List of search results
        """
        raise NotImplementedError("Phase 5, Step 5.1")

    def get_remaining_quota(self) -> int:
        """Return remaining searches for today.

        Returns:
            Number of searches remaining (max 100)
        """
        today = date.today()
        if self._query_date != today:
            self._queries_today = 0
            self._query_date = today
        return max(0, 100 - self._queries_today)

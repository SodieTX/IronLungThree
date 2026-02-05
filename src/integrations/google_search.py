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

import requests  # type: ignore[import-untyped]

from src.core.exceptions import IntegrationError
from src.core.logging import get_logger
from src.integrations.base import IntegrationBase

logger = get_logger(__name__)

GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"


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
            api_key: Google API key (optional, uses config if not provided)
            cx: Custom Search Engine ID (optional, uses config if not provided)
        """
        from src.core.config import get_config

        config = get_config()
        self._api_key = api_key or config.google_api_key
        self._cx = cx or config.google_cx
        self._queries_today = 0
        self._query_date: Optional[date] = None
        self._cache: dict[str, list[SearchResult]] = {}

    def health_check(self) -> bool:
        """Check if Google Search API is reachable.

        Performs a minimal test query to verify credentials.

        Returns:
            True if API is reachable and authenticated
        """
        if not self.is_configured():
            return False

        try:
            response = requests.get(
                GOOGLE_CSE_URL,
                params={
                    "key": self._api_key,
                    "cx": self._cx,
                    "q": "test",
                    "num": 1,
                },
                timeout=10,
            )
            return bool(response.status_code == 200)
        except requests.RequestException:
            return False

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

        Raises:
            IntegrationError: If search fails or quota exceeded
        """
        if not self.is_configured():
            raise IntegrationError("Google Search not configured (missing API key or CX)")

        remaining = self.get_remaining_quota()
        if remaining <= 0:
            logger.warning("Google Search daily quota exhausted")
            raise IntegrationError("Google Search daily quota exhausted (100/day)")

        # Check cache first
        cache_key = f"{query}:{num_results}"
        if cache_key in self._cache:
            logger.debug(f"Google Search cache hit: {query}")
            return self._cache[cache_key]

        # Clamp to API maximum
        num_results = min(num_results, 10)

        try:
            response = self.with_retry(
                lambda: requests.get(
                    GOOGLE_CSE_URL,
                    params={
                        "key": self._api_key,
                        "cx": self._cx,
                        "q": query,
                        "num": num_results,
                    },
                    timeout=15,
                ),
                max_retries=2,
                exceptions=(requests.RequestException,),
            )

            # Track quota
            self._queries_today += 1
            self._query_date = date.today()

            if response.status_code == 429:
                raise IntegrationError("Google Search rate limit exceeded")

            if response.status_code != 200:
                raise IntegrationError(
                    f"Google Search failed ({response.status_code}): {response.text[:200]}"
                )

            data = response.json()
            results: list[SearchResult] = []

            for item in data.get("items", []):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                    )
                )

            # Cache results
            self._cache[cache_key] = results

            logger.info(
                "Google search completed",
                extra={
                    "context": {
                        "query": query,
                        "results": len(results),
                        "remaining_quota": self.get_remaining_quota(),
                    }
                },
            )

            return results

        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"Google Search error: {e}") from e

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

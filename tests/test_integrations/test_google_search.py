"""Tests for Google Custom Search integration (src/integrations/google_search.py).

Covers:
    - GoogleSearchClient.is_configured: with and without credentials
    - GoogleSearchClient.get_remaining_quota: quota tracking
    - GoogleSearchClient.search: raises IntegrationError when not configured
"""

from datetime import date
from unittest.mock import patch

import pytest

from src.core.exceptions import IntegrationError
from src.integrations.google_search import GoogleSearchClient

# ===========================================================================
# is_configured
# ===========================================================================


class TestIsConfigured:
    """Credential presence check."""

    def test_not_configured_without_credentials(self):
        """Returns False when both api_key and cx are None."""
        client = GoogleSearchClient(api_key=None, cx=None)
        assert client.is_configured() is False

    def test_not_configured_with_only_api_key(self):
        """Returns False when only api_key is provided."""
        client = GoogleSearchClient(api_key="some-key", cx=None)
        assert client.is_configured() is False

    def test_not_configured_with_only_cx(self):
        """Returns False when only cx is provided."""
        client = GoogleSearchClient(api_key=None, cx="some-cx")
        assert client.is_configured() is False

    def test_configured_with_both(self):
        """Returns True when both api_key and cx are provided."""
        client = GoogleSearchClient(api_key="test-key", cx="test-cx")
        assert client.is_configured() is True

    def test_not_configured_with_empty_strings(self):
        """Returns False when credentials are empty strings."""
        client = GoogleSearchClient(api_key="", cx="")
        assert client.is_configured() is False


# ===========================================================================
# get_remaining_quota
# ===========================================================================


class TestGetRemainingQuota:
    """Quota tracking (100 per day)."""

    def test_fresh_client_has_100(self):
        """New client has full quota of 100."""
        client = GoogleSearchClient(api_key="k", cx="c")
        assert client.get_remaining_quota() == 100

    def test_quota_decrements(self):
        """Manually incrementing _queries_today reduces remaining."""
        client = GoogleSearchClient(api_key="k", cx="c")
        client._queries_today = 10
        client._query_date = date.today()
        assert client.get_remaining_quota() == 90

    def test_quota_resets_on_new_day(self):
        """Quota resets to 100 when date changes."""
        client = GoogleSearchClient(api_key="k", cx="c")
        client._queries_today = 50
        client._query_date = date(2020, 1, 1)  # Old date

        remaining = client.get_remaining_quota()
        assert remaining == 100
        assert client._queries_today == 0

    def test_quota_floors_at_zero(self):
        """Quota never goes negative."""
        client = GoogleSearchClient(api_key="k", cx="c")
        client._queries_today = 150
        client._query_date = date.today()
        assert client.get_remaining_quota() == 0


# ===========================================================================
# search
# ===========================================================================


class TestSearch:
    """Search execution."""

    def test_raises_when_not_configured(self):
        """search() raises IntegrationError when credentials are missing."""
        client = GoogleSearchClient(api_key=None, cx=None)
        with pytest.raises(IntegrationError, match="not configured"):
            client.search("test query")

    def test_raises_when_quota_exhausted(self):
        """search() raises IntegrationError when daily quota is 0."""
        client = GoogleSearchClient(api_key="k", cx="c")
        client._queries_today = 100
        client._query_date = date.today()

        with pytest.raises(IntegrationError, match="quota exhausted"):
            client.search("test query")

    def test_cache_hit_returns_cached_results(self):
        """Cached queries are returned without API call."""
        from src.integrations.google_search import SearchResult

        client = GoogleSearchClient(api_key="k", cx="c")
        # Pre-populate cache
        cached = [SearchResult(title="Cached", url="http://ex.com", snippet="cached")]
        client._cache["test query:10"] = cached

        results = client.search("test query")
        assert len(results) == 1
        assert results[0].title == "Cached"

"""ActiveCampaign API integration.

Pulls new prospects from ActiveCampaign pipelines.

Usage:
    from src.integrations.activecampaign import ActiveCampaignClient

    client = ActiveCampaignClient()
    contacts = client.get_contacts(since=last_sync)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.core.config import get_config
from src.core.logging import get_logger
from src.integrations.base import IntegrationBase, RateLimiter

logger = get_logger(__name__)


@dataclass
class ACContact:
    """Contact from ActiveCampaign.

    Attributes:
        id: AC contact ID
        email: Email address
        first_name: First name
        last_name: Last name
        phone: Phone number
        company: Company name
        created_at: When created in AC
    """

    id: str
    email: str
    first_name: str = ""
    last_name: str = ""
    phone: Optional[str] = None
    company: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class ACPipeline:
    """Pipeline from ActiveCampaign.

    Attributes:
        id: Pipeline ID
        name: Pipeline name
    """

    id: int
    name: str


class ActiveCampaignClient(IntegrationBase):
    """ActiveCampaign API client.

    Used during nightly cycle to pull new prospects.
    """

    def __init__(self):
        """Initialize AC client."""
        self._config = get_config()
        self._rate_limiter = RateLimiter(calls_per_minute=60)

    def health_check(self) -> bool:
        """Check if AC API is reachable."""
        raise NotImplementedError("Phase 5, Step 5.7")

    def is_configured(self) -> bool:
        """Check if AC credentials are configured."""
        return bool(self._config.activecampaign_api_key and self._config.activecampaign_url)

    def get_contacts(
        self,
        pipeline_id: Optional[int] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[ACContact]:
        """Get contacts from ActiveCampaign.

        Args:
            pipeline_id: Filter by pipeline (optional)
            since: Only contacts created after this time
            limit: Maximum contacts to return

        Returns:
            List of AC contacts
        """
        raise NotImplementedError("Phase 5, Step 5.7")

    def get_pipelines(self) -> list[ACPipeline]:
        """List available pipelines.

        Returns:
            List of pipelines
        """
        raise NotImplementedError("Phase 5, Step 5.7")

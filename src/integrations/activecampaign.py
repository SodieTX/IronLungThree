"""ActiveCampaign API integration.

Pulls new prospects from ActiveCampaign pipelines.

Usage:
    from src.integrations.activecampaign import ActiveCampaignClient

    client = ActiveCampaignClient()
    contacts = client.get_contacts(since=last_sync)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import requests  # type: ignore[import-untyped]

from src.core.config import get_config
from src.core.exceptions import IntegrationError
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

    def __init__(self) -> None:
        """Initialize AC client."""
        self._config = get_config()
        self._rate_limiter = RateLimiter(calls_per_minute=60)

    @property
    def _api_key(self) -> Optional[str]:
        """Get API key from config."""
        return self._config.activecampaign_api_key

    @property
    def _base_url(self) -> Optional[str]:
        """Get base URL from config."""
        url = self._config.activecampaign_url
        if url and url.endswith("/"):
            url = url[:-1]
        return url

    def health_check(self) -> bool:
        """Check if AC API is reachable.

        Returns:
            True if API responds successfully
        """
        if not self.is_configured():
            return False

        try:
            response = self._api_request("GET", "/api/3/contacts", params={"limit": 1})
            return bool(response.status_code == 200)
        except (IntegrationError, requests.RequestException):
            return False

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

        Raises:
            IntegrationError: If API call fails
        """
        if not self.is_configured():
            raise IntegrationError("ActiveCampaign not configured")

        params: dict[str, Any] = {"limit": min(limit, 100)}

        if since:
            params["filters[created_after]"] = since.strftime("%Y-%m-%dT%H:%M:%S-00:00")

        contacts: list[ACContact] = []
        offset = 0

        while len(contacts) < limit:
            params["offset"] = offset

            try:
                self._rate_limiter.wait_if_needed()
                response = self._api_request("GET", "/api/3/contacts", params=params)

                if response.status_code != 200:
                    raise IntegrationError(
                        f"AC API error ({response.status_code}): {response.text[:200]}"
                    )

                data = response.json()
                batch = data.get("contacts", [])

                if not batch:
                    break

                for contact_data in batch:
                    created = None
                    if contact_data.get("cdate"):
                        try:
                            created = datetime.fromisoformat(
                                contact_data["cdate"].replace("T", " ").split("+")[0]
                            )
                        except (ValueError, IndexError):
                            pass

                    contacts.append(
                        ACContact(
                            id=str(contact_data.get("id", "")),
                            email=contact_data.get("email", ""),
                            first_name=contact_data.get("firstName", ""),
                            last_name=contact_data.get("lastName", ""),
                            phone=contact_data.get("phone") or None,
                            company=None,  # Requires separate org lookup
                            created_at=created,
                        )
                    )

                offset += len(batch)

                # Stop if we got fewer than requested (no more pages)
                if len(batch) < params["limit"]:
                    break

            except IntegrationError:
                raise
            except Exception as e:
                raise IntegrationError(f"AC contact fetch error: {e}") from e

        logger.info(
            "ActiveCampaign contacts fetched",
            extra={
                "context": {
                    "count": len(contacts),
                    "since": str(since),
                    "pipeline_id": pipeline_id,
                }
            },
        )

        return contacts[:limit]

    def get_pipelines(self) -> list[ACPipeline]:
        """List available pipelines.

        Returns:
            List of pipelines

        Raises:
            IntegrationError: If API call fails
        """
        if not self.is_configured():
            raise IntegrationError("ActiveCampaign not configured")

        try:
            self._rate_limiter.wait_if_needed()
            response = self._api_request("GET", "/api/3/dealGroups")

            if response.status_code != 200:
                raise IntegrationError(
                    f"AC API error ({response.status_code}): {response.text[:200]}"
                )

            data = response.json()
            pipelines: list[ACPipeline] = []

            for group in data.get("dealGroups", []):
                pipelines.append(
                    ACPipeline(
                        id=int(group.get("id", 0)),
                        name=group.get("title", ""),
                    )
                )

            logger.info(
                "ActiveCampaign pipelines fetched",
                extra={"context": {"count": len(pipelines)}},
            )

            return pipelines

        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"AC pipeline fetch error: {e}") from e

    def _api_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> requests.Response:
        """Make authenticated API request to ActiveCampaign.

        Args:
            method: HTTP method
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON body

        Returns:
            Response object

        Raises:
            IntegrationError: If request fails
        """
        if not self._base_url or not self._api_key:
            raise IntegrationError("ActiveCampaign not configured")

        url = f"{self._base_url}{endpoint}"
        headers = {
            "Api-Token": self._api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            return self.with_retry(
                lambda: requests.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    timeout=30,
                ),
                max_retries=2,
                exceptions=(requests.RequestException,),
            )
        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"AC API request failed: {e}") from e

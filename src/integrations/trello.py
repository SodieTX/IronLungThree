"""Trello API integration for task/board management.

Connects to Trello boards for syncing prospect-related tasks
and tracking pipeline activity on a shared board.

Usage:
    from src.integrations.trello import TrelloClient

    client = TrelloClient()
    boards = client.get_boards()
    lists = client.get_lists(board_id)
    cards = client.get_cards(list_id)
"""

from dataclasses import dataclass
from typing import Any, Optional

import requests  # type: ignore[import-untyped]

from src.core.config import get_config
from src.core.exceptions import IntegrationError
from src.core.logging import get_logger
from src.integrations.base import IntegrationBase, RateLimiter

logger = get_logger(__name__)

TRELLO_API_BASE = "https://api.trello.com/1"


@dataclass
class TrelloBoard:
    """Trello board.

    Attributes:
        id: Board ID
        name: Board name
        url: Board URL
    """

    id: str
    name: str
    url: str


@dataclass
class TrelloList:
    """Trello list (column on a board).

    Attributes:
        id: List ID
        name: List name
        board_id: Parent board ID
    """

    id: str
    name: str
    board_id: str


@dataclass
class TrelloCard:
    """Trello card.

    Attributes:
        id: Card ID
        name: Card name
        description: Card description
        list_id: Parent list ID
        url: Card URL
        labels: Label names on this card
    """

    id: str
    name: str
    description: str
    list_id: str
    url: str
    labels: list[str]


class TrelloClient(IntegrationBase):
    """Trello API client.

    Used for syncing tasks and tracking prospect pipeline on a Trello board.
    """

    def __init__(self) -> None:
        self._config = get_config()
        self._rate_limiter = RateLimiter(calls_per_minute=100)

    @property
    def _api_key(self) -> Optional[str]:
        return self._config.trello_api_key

    @property
    def _token(self) -> Optional[str]:
        return self._config.trello_token

    @property
    def _board_id(self) -> Optional[str]:
        return self._config.trello_board_id

    def health_check(self) -> bool:
        """Check if Trello API is reachable.

        Returns:
            True if API responds successfully
        """
        if not self.is_configured():
            return False

        try:
            response = self._api_request("GET", "/members/me")
            return bool(response.status_code == 200)
        except (IntegrationError, requests.RequestException):
            return False

    def is_configured(self) -> bool:
        """Check if Trello credentials are configured."""
        return bool(self._api_key and self._token)

    def get_boards(self) -> list[TrelloBoard]:
        """Get all boards accessible to the authenticated user.

        Returns:
            List of Trello boards

        Raises:
            IntegrationError: If API call fails
        """
        if not self.is_configured():
            raise IntegrationError("Trello not configured")

        try:
            self._rate_limiter.wait_if_needed()
            response = self._api_request(
                "GET", "/members/me/boards", params={"fields": "name,url"}
            )

            if response.status_code != 200:
                raise IntegrationError(
                    f"Trello API error ({response.status_code}): {response.text[:200]}"
                )

            boards: list[TrelloBoard] = []
            for board_data in response.json():
                boards.append(
                    TrelloBoard(
                        id=board_data.get("id", ""),
                        name=board_data.get("name", ""),
                        url=board_data.get("url", ""),
                    )
                )

            logger.info(
                "Trello boards fetched",
                extra={"context": {"count": len(boards)}},
            )
            return boards

        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"Trello boards fetch error: {e}") from e

    def get_lists(self, board_id: Optional[str] = None) -> list[TrelloList]:
        """Get all lists on a board.

        Args:
            board_id: Board ID (uses configured board if not provided)

        Returns:
            List of Trello lists

        Raises:
            IntegrationError: If API call fails
        """
        if not self.is_configured():
            raise IntegrationError("Trello not configured")

        bid = board_id or self._board_id
        if not bid:
            raise IntegrationError("No board ID provided or configured (TRELLO_BOARD_ID)")

        try:
            self._rate_limiter.wait_if_needed()
            response = self._api_request(
                "GET", f"/boards/{bid}/lists", params={"fields": "name,idBoard"}
            )

            if response.status_code != 200:
                raise IntegrationError(
                    f"Trello API error ({response.status_code}): {response.text[:200]}"
                )

            lists: list[TrelloList] = []
            for list_data in response.json():
                lists.append(
                    TrelloList(
                        id=list_data.get("id", ""),
                        name=list_data.get("name", ""),
                        board_id=list_data.get("idBoard", ""),
                    )
                )

            logger.info(
                "Trello lists fetched",
                extra={"context": {"board_id": bid, "count": len(lists)}},
            )
            return lists

        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"Trello lists fetch error: {e}") from e

    def get_cards(self, list_id: str) -> list[TrelloCard]:
        """Get all cards in a list.

        Args:
            list_id: List ID

        Returns:
            List of Trello cards

        Raises:
            IntegrationError: If API call fails
        """
        if not self.is_configured():
            raise IntegrationError("Trello not configured")

        try:
            self._rate_limiter.wait_if_needed()
            response = self._api_request(
                "GET",
                f"/lists/{list_id}/cards",
                params={"fields": "name,desc,idList,url,labels"},
            )

            if response.status_code != 200:
                raise IntegrationError(
                    f"Trello API error ({response.status_code}): {response.text[:200]}"
                )

            cards: list[TrelloCard] = []
            for card_data in response.json():
                labels = [
                    label.get("name", "") for label in card_data.get("labels", [])
                ]
                cards.append(
                    TrelloCard(
                        id=card_data.get("id", ""),
                        name=card_data.get("name", ""),
                        description=card_data.get("desc", ""),
                        list_id=card_data.get("idList", ""),
                        url=card_data.get("url", ""),
                        labels=labels,
                    )
                )

            logger.info(
                "Trello cards fetched",
                extra={"context": {"list_id": list_id, "count": len(cards)}},
            )
            return cards

        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"Trello cards fetch error: {e}") from e

    def create_card(
        self,
        list_id: str,
        name: str,
        description: str = "",
    ) -> TrelloCard:
        """Create a new card in a list.

        Args:
            list_id: List ID to create the card in
            name: Card name
            description: Card description

        Returns:
            Created TrelloCard

        Raises:
            IntegrationError: If API call fails
        """
        if not self.is_configured():
            raise IntegrationError("Trello not configured")

        try:
            self._rate_limiter.wait_if_needed()
            response = self._api_request(
                "POST",
                "/cards",
                params={
                    "idList": list_id,
                    "name": name,
                    "desc": description,
                },
            )

            if response.status_code not in (200, 201):
                raise IntegrationError(
                    f"Trello API error ({response.status_code}): {response.text[:200]}"
                )

            card_data = response.json()
            card = TrelloCard(
                id=card_data.get("id", ""),
                name=card_data.get("name", ""),
                description=card_data.get("desc", ""),
                list_id=card_data.get("idList", ""),
                url=card_data.get("url", ""),
                labels=[
                    label.get("name", "") for label in card_data.get("labels", [])
                ],
            )

            logger.info(
                "Trello card created",
                extra={"context": {"card_id": card.id, "list_id": list_id}},
            )
            return card

        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"Trello card create error: {e}") from e

    def move_card(self, card_id: str, target_list_id: str) -> None:
        """Move a card to a different list.

        Args:
            card_id: Card ID to move
            target_list_id: Destination list ID

        Raises:
            IntegrationError: If API call fails
        """
        if not self.is_configured():
            raise IntegrationError("Trello not configured")

        try:
            self._rate_limiter.wait_if_needed()
            response = self._api_request(
                "PUT",
                f"/cards/{card_id}",
                params={"idList": target_list_id},
            )

            if response.status_code != 200:
                raise IntegrationError(
                    f"Trello API error ({response.status_code}): {response.text[:200]}"
                )

            logger.info(
                "Trello card moved",
                extra={"context": {"card_id": card_id, "target_list": target_list_id}},
            )

        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"Trello card move error: {e}") from e

    def _api_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
    ) -> requests.Response:
        """Make authenticated API request to Trello.

        Args:
            method: HTTP method
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            Response object

        Raises:
            IntegrationError: If request fails
        """
        if not self._api_key or not self._token:
            raise IntegrationError("Trello not configured")

        url = f"{TRELLO_API_BASE}{endpoint}"

        # Trello uses query-param auth
        auth_params = {"key": self._api_key, "token": self._token}
        if params:
            auth_params.update(params)

        try:
            return self.with_retry(
                lambda: requests.request(
                    method,
                    url,
                    params=auth_params,
                    timeout=30,
                ),
                max_retries=2,
                exceptions=(requests.RequestException,),
            )
        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"Trello API request failed: {e}") from e

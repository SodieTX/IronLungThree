"""Anne - The conversational AI assistant.

Anne is the product. She:
    - Presents cards with context and recommendations
    - Discusses prospects with Jeff
    - Takes obsessive notes
    - Drafts emails in Jeff's voice
    - Can disagree when warranted
    - Executes after confirmation

Usage:
    from src.ai.anne import Anne

    anne = Anne(db)
    presentation = anne.present_card(prospect_id)
    response = anne.respond(user_input, context)
"""

from dataclasses import dataclass
from typing import Any, Optional

from src.core.config import get_config
from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Company, Prospect

logger = get_logger(__name__)


@dataclass
class AnneResponse:
    """Anne's response to user input.

    Attributes:
        message: Anne's spoken/displayed message
        suggested_actions: Actions Anne suggests
        requires_confirmation: Whether to wait for confirm
        disposition: Suggested disposition if any
    """

    message: str
    suggested_actions: Optional[list[dict]] = None
    requires_confirmation: bool = False
    disposition: Optional[str] = None


@dataclass
class ConversationContext:
    """Context for Anne's conversation.

    Attributes:
        current_prospect_id: Current card being discussed
        recent_messages: Recent conversation history
        mode: Current mode (processing, copilot, etc.)
    """

    current_prospect_id: Optional[int] = None
    recent_messages: Optional[list[dict]] = None
    mode: str = "processing"


class Anne:
    """Anne - The conversational AI assistant."""

    def __init__(self, db: Database):
        """Initialize Anne."""
        self.db = db
        self._config = get_config()

    def is_available(self) -> bool:
        """Check if Anne (Claude API) is available."""
        return bool(self._config.claude_api_key)

    def present_card(self, prospect_id: int) -> str:
        """Generate card presentation with context and recommendation."""
        raise NotImplementedError("Phase 4, Step 4.3")

    def respond(self, user_input: str, context: ConversationContext) -> AnneResponse:
        """Process user input and respond."""
        raise NotImplementedError("Phase 4, Step 4.3")

    def execute_actions(self, actions: list[dict]) -> dict:
        """Execute confirmed actions."""
        raise NotImplementedError("Phase 4, Step 4.3")

    def pre_generate_cards(self, prospect_ids: list[int]) -> dict[int, str]:
        """Batch-generate card presentations for queue."""
        raise NotImplementedError("Phase 4, Step 4.9")

    def take_notes(self, prospect_id: int, conversation: str) -> str:
        """Generate obsessive notes from conversation."""
        raise NotImplementedError("Phase 4, Step 4.5")

    def extract_intel(self, prospect_id: int, notes: str) -> list[dict]:
        """Extract intel nuggets from notes."""
        raise NotImplementedError("Phase 4, Step 4.5")

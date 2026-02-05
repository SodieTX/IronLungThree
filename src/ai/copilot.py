"""AI Copilot for strategic conversation mode.

Deeper conversational mode for questions like:
    - "What's our pipeline looking like?"
    - "What's the story with ABC Lending?"
    - "I've got a demo tomorrow, what should I know?"
"""

from src.core.logging import get_logger
from src.db.database import Database

logger = get_logger(__name__)


class Copilot:
    """Strategic AI conversation mode."""

    def __init__(self, db: Database):
        self.db = db

    def ask(self, question: str) -> str:
        """Answer strategic question about pipeline."""
        raise NotImplementedError("Phase 7, Step 7.1")

    def pipeline_summary(self) -> str:
        """Generate pipeline overview."""
        raise NotImplementedError("Phase 7, Step 7.1")

    def company_story(self, company_id: int) -> str:
        """Generate company/prospect story."""
        raise NotImplementedError("Phase 7, Step 7.1")

    def demo_briefing(self, prospect_id: int) -> str:
        """Generate pre-demo briefing."""
        raise NotImplementedError("Phase 7, Step 7.1")

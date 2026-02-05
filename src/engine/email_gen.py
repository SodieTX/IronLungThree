"""AI-powered email generation using Claude.

Generates ad-hoc emails based on Jeff's instruction and prospect context.
Uses style learner to match Jeff's voice.

Usage:
    from src.engine.email_gen import EmailGenerator

    gen = EmailGenerator()
    draft = gen.generate_email(
        prospect=p,
        instruction="Short intro, mention we work with fix-and-flip shops"
    )
"""

from dataclasses import dataclass
from typing import Optional

from src.db.models import Prospect, Company
from src.core.config import get_config
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class GeneratedEmail:
    """AI-generated email.

    Attributes:
        subject: Email subject
        body: Email body (plain text)
        body_html: Email body (HTML)
        tokens_used: API tokens consumed
    """

    subject: str
    body: str
    body_html: Optional[str] = None
    tokens_used: int = 0


class EmailGenerator:
    """AI email generation with Jeff's voice.

    Uses Claude API with style examples to generate
    contextually appropriate emails.
    """

    def __init__(self, style_examples: Optional[list[str]] = None):
        """Initialize email generator.

        Args:
            style_examples: Jeff's example emails for style matching
        """
        self._config = get_config()
        self._style_examples = style_examples or []

    def is_available(self) -> bool:
        """Check if Claude API is available."""
        return bool(self._config.claude_api_key)

    def generate_email(
        self,
        prospect: Prospect,
        company: Company,
        instruction: str,
        context: Optional[str] = None,
    ) -> GeneratedEmail:
        """Generate email based on instruction.

        Args:
            prospect: Target prospect
            company: Prospect's company
            instruction: Jeff's instruction ("short intro", "follow up on demo")
            context: Additional context (recent notes, etc.)

        Returns:
            Generated email
        """
        raise NotImplementedError("Phase 3, Step 3.6")

    def refine_email(
        self,
        draft: str,
        feedback: str,
    ) -> GeneratedEmail:
        """Refine a draft based on feedback.

        Args:
            draft: Current draft
            feedback: Jeff's feedback ("make it shorter", "more casual")

        Returns:
            Refined email
        """
        raise NotImplementedError("Phase 3, Step 3.6")

    def _build_prompt(
        self,
        prospect: Prospect,
        company: Company,
        instruction: str,
        context: Optional[str],
    ) -> str:
        """Build prompt for Claude."""
        raise NotImplementedError("Phase 3, Step 3.6")

    def _get_style_guidance(self) -> str:
        """Generate style guidance from examples."""
        raise NotImplementedError("Phase 3, Step 3.6")

"""AI-powered email generation using Claude.

Generates ad-hoc emails based on Jeff's instruction and prospect context.
Uses style learner to match Jeff's voice.

Usage:
    from src.engine.email_gen import EmailGenerator

    gen = EmailGenerator()
    draft = gen.generate_email(
        prospect=p,
        company=c,
        instruction="Short intro, mention we work with fix-and-flip shops"
    )
"""

from dataclasses import dataclass
from typing import Optional

from src.ai.claude_client import ClaudeClientMixin
from src.core.config import CLAUDE_MODEL, get_config
from src.core.logging import get_logger
from src.db.models import Company, Prospect

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


class EmailGenerator(ClaudeClientMixin):
    """AI email generation with Jeff's voice.

    Uses Claude API with style examples to generate
    contextually appropriate emails.
    """

    def __init__(self, style_examples: Optional[list[str]] = None) -> None:
        """Initialize email generator.

        Args:
            style_examples: Jeff's example emails for style matching
        """
        self._config = get_config()
        self._style_examples = style_examples or []
        self._client: Optional[object] = None

    def _get_claude_config(self):
        return self._config

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
            Generated email with subject, body, and token usage
        """
        prompt = self._build_prompt(prospect, company, instruction, context)
        return self._call_api(prompt)

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
        prompt = (
            f"Here is an email draft I wrote:\n\n{draft}\n\n"
            f"Please revise it with this feedback: {feedback}\n\n"
            "Return the revised email in the same format:\n"
            "SUBJECT: ...\nBODY:\n..."
        )
        return self._call_api(prompt)

    def _call_api(self, prompt: str) -> GeneratedEmail:
        """Call Claude API and parse the response.

        Args:
            prompt: Full prompt to send

        Returns:
            Parsed GeneratedEmail
        """
        client = self._get_client()

        response = client.messages.create(  # type: ignore[attr-defined]
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text  # type: ignore[attr-defined]
        tokens_used = (
            response.usage.input_tokens + response.usage.output_tokens  # type: ignore[attr-defined]
        )
        self._track_usage(
            "email_gen",
            CLAUDE_MODEL,
            response.usage.input_tokens,  # type: ignore[attr-defined]
            response.usage.output_tokens,  # type: ignore[attr-defined]
        )

        return self._parse_response(text, tokens_used)

    def _parse_response(self, text: str, tokens_used: int) -> GeneratedEmail:
        """Parse Claude's response into subject and body.

        Expected format:
            SUBJECT: <subject line>
            BODY:
            <email body>
        """
        subject = ""
        body = text

        lines = text.strip().split("\n")
        for i, line in enumerate(lines):
            if line.startswith("SUBJECT:"):
                subject = line[len("SUBJECT:") :].strip()
            elif line.startswith("BODY:"):
                body = "\n".join(lines[i + 1 :]).strip()
                break

        return GeneratedEmail(
            subject=subject,
            body=body,
            tokens_used=tokens_used,
        )

    def _build_prompt(
        self,
        prospect: Prospect,
        company: Company,
        instruction: str,
        context: Optional[str],
    ) -> str:
        """Build prompt for Claude with prospect context."""
        style_guidance = self._get_style_guidance()

        parts = [
            "You are an email ghostwriter for a sales professional "
            "in the private lending / loan origination software space.",
            "",
            f"Prospect: {prospect.first_name} {prospect.last_name}",
            f"Title: {prospect.title or 'Unknown'}",
            f"Company: {company.name}",
        ]

        if company.state:
            parts.append(f"Location: {company.state}")
        if company.size:
            parts.append(f"Company Size: {company.size}")

        parts.append("")
        parts.append(f"Instruction: {instruction}")

        if context:
            parts.append(f"\nAdditional context:\n{context}")

        if style_guidance:
            parts.append(f"\n{style_guidance}")

        parts.extend(
            [
                "",
                "Write the email in this format:",
                "SUBJECT: <subject line>",
                "BODY:",
                "<email body>",
                "",
                "Keep it concise, professional, and conversational. "
                "No fluff or buzzwords. Sound like a real person.",
            ]
        )

        return "\n".join(parts)

    def _get_style_guidance(self) -> str:
        """Generate style guidance from Jeff's example emails."""
        if not self._style_examples:
            return ""

        examples_text = "\n---\n".join(self._style_examples[:3])
        return (
            f"Here are example emails that show the writer's voice "
            f"and style. Match this tone:\n\n{examples_text}"
        )

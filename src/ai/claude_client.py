"""Shared Claude API client mixin.

Eliminates duplicated _get_client() / is_available() boilerplate
across Anne, Copilot, and EmailGenerator.
"""

from typing import Any, Optional

from src.core.config import get_config
from src.core.logging import get_logger

logger = get_logger(__name__)


class ClaudeClientMixin:
    """Mixin providing lazy Anthropic client initialization.

    Classes using this mixin must NOT define their own ``_client`` attribute
    before calling ``super().__init__()`` (or should set ``self._client = None``
    in their own ``__init__``).
    """

    _client: Optional[object] = None

    def _get_claude_config(self):
        """Return the app config (override if config is stored differently)."""
        return get_config()

    def is_available(self) -> bool:
        """Check if the Claude API key is configured."""
        return bool(self._get_claude_config().claude_api_key)

    def _get_client(self) -> Any:
        """Get or create the Anthropic client (lazy singleton)."""
        if self._client is None:
            config = self._get_claude_config()
            if not config.claude_api_key:
                raise RuntimeError("CLAUDE_API_KEY not configured")
            try:
                import anthropic

                self._client = anthropic.Anthropic(api_key=config.claude_api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. Install with: pip install anthropic"
                )
        return self._client

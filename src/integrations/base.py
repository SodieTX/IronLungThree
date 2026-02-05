"""Base classes for external integrations.

All integrations inherit from IntegrationBase, which provides:
    - Health check interface
    - Configuration check
    - Rate limiting
    - Retry with exponential backoff
    - Logging patterns
"""

from abc import ABC, abstractmethod
from typing import Callable, Any, Optional, TypeVar
import time

from src.core.exceptions import IntegrationError
from src.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class IntegrationBase(ABC):
    """Abstract base class for all external integrations.

    Subclasses must implement:
        - health_check(): Check if service is available
        - is_configured(): Check if credentials are present
    """

    @abstractmethod
    def health_check(self) -> bool:
        """Check if integration is healthy and available.

        Returns:
            True if service is reachable and functioning
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if required credentials/configuration are present.

        Returns:
            True if all required config is present
        """
        pass

    def with_retry(
        self,
        func: Callable[..., T],
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exceptions: tuple = (Exception,),
    ) -> T:
        """Execute function with exponential backoff retry.

        Args:
            func: Function to execute
            max_retries: Maximum retry attempts
            base_delay: Initial delay between retries (seconds)
            max_delay: Maximum delay between retries
            exceptions: Exception types to catch and retry

        Returns:
            Function result

        Raises:
            IntegrationError: If all retries exhausted
        """
        last_exception: Optional[Exception] = None
        delay = base_delay

        for attempt in range(max_retries + 1):
            try:
                return func()
            except exceptions as e:
                last_exception = e
                if attempt < max_retries:
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} after {delay}s: {e}",
                        extra={"context": {"attempt": attempt + 1}},
                    )
                    time.sleep(delay)
                    delay = min(delay * 2, max_delay)

        raise IntegrationError(
            f"Operation failed after {max_retries + 1} attempts: {last_exception}"
        ) from last_exception


class RateLimiter:
    """Simple rate limiter for API calls.

    Attributes:
        calls_per_minute: Maximum calls allowed per minute
    """

    def __init__(self, calls_per_minute: int = 60):
        """Initialize rate limiter.

        Args:
            calls_per_minute: Maximum calls per minute
        """
        self.calls_per_minute = calls_per_minute
        self._call_times: list[float] = []

    def wait_if_needed(self) -> None:
        """Wait if rate limit would be exceeded."""
        now = time.time()

        # Remove calls older than 1 minute
        self._call_times = [t for t in self._call_times if now - t < 60]

        if len(self._call_times) >= self.calls_per_minute:
            # Wait until oldest call expires
            sleep_time = 60 - (now - self._call_times[0])
            if sleep_time > 0:
                logger.debug(f"Rate limit: sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)

        self._call_times.append(time.time())

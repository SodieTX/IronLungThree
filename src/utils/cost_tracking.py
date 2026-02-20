"""Claude API cost tracking.

Tracks every API call: model, tokens, estimated cost.
Accumulates daily and monthly totals. Persists to JSONL file.

Usage:
    from src.utils.cost_tracking import get_cost_tracker

    tracker = get_cost_tracker()
    tracker.record_call("anne", "claude-sonnet-4-20250514", 1500, 300)
    print(tracker.get_today_summary())
"""

import json
import threading
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)

# Default usage file location
DEFAULT_USAGE_FILE = Path.home() / ".ironlung" / "api_usage.jsonl"

# Pricing per million tokens (update as pricing changes)
# Format: model_prefix -> (input_cost_per_M, output_cost_per_M)
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus": (15.0, 75.0),
    "claude-sonnet": (3.0, 15.0),
    "claude-haiku": (0.25, 1.25),
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost for an API call based on model and token counts.

    Args:
        model: Model name (e.g. "claude-sonnet-4-20250514")
        input_tokens: Input token count
        output_tokens: Output token count

    Returns:
        Estimated cost in USD
    """
    for prefix, (input_rate, output_rate) in _MODEL_PRICING.items():
        if prefix in model:
            return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
    # Unknown model — use sonnet pricing as conservative default
    return (input_tokens * 3.0 + output_tokens * 15.0) / 1_000_000


@dataclass
class APICallRecord:
    """A single API call record.

    Attributes:
        timestamp: ISO timestamp of the call
        caller: Module that made the call (anne, copilot, email_gen)
        model: Claude model used
        input_tokens: Input tokens consumed
        output_tokens: Output tokens consumed
        estimated_cost: Estimated cost in USD
    """

    timestamp: str
    caller: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float


@dataclass
class UsageSummary:
    """Aggregated usage summary.

    Attributes:
        period: Description of the period (e.g. "2026-02-20", "2026-02")
        total_calls: Number of API calls
        total_input_tokens: Total input tokens
        total_output_tokens: Total output tokens
        total_cost: Total estimated cost in USD
        by_caller: Breakdown by caller module
    """

    period: str
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    by_caller: dict[str, float] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.by_caller is None:
            self.by_caller = {}


class CostTracker:
    """Tracks Claude API usage and costs.

    Thread-safe. Appends records to a JSONL file.

    Attributes:
        usage_file: Path to the JSONL usage file
    """

    def __init__(self, usage_file: Optional[Path] = None):
        """Initialize cost tracker.

        Args:
            usage_file: Path to JSONL file. Defaults to ~/.ironlung/api_usage.jsonl
        """
        self.usage_file = usage_file or DEFAULT_USAGE_FILE
        self._lock = threading.Lock()

    def record_call(
        self,
        caller: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> APICallRecord:
        """Record an API call.

        Args:
            caller: Module name (e.g. "anne", "copilot", "email_gen")
            model: Claude model used
            input_tokens: Input tokens consumed
            output_tokens: Output tokens consumed

        Returns:
            The recorded APICallRecord
        """
        cost = _estimate_cost(model, input_tokens, output_tokens)
        record = APICallRecord(
            timestamp=datetime.now().isoformat(),
            caller=caller,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=round(cost, 6),
        )

        with self._lock:
            self.usage_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.usage_file, "a") as f:
                f.write(json.dumps(asdict(record)) + "\n")

        logger.debug(
            "API call recorded",
            extra={
                "context": {
                    "caller": caller,
                    "tokens": input_tokens + output_tokens,
                    "cost": record.estimated_cost,
                }
            },
        )

        return record

    def _read_records(self) -> list[APICallRecord]:
        """Read all records from the usage file."""
        if not self.usage_file.exists():
            return []

        records = []
        with open(self.usage_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    records.append(APICallRecord(**data))
                except (json.JSONDecodeError, TypeError):
                    continue
        return records

    def get_today_summary(self) -> UsageSummary:
        """Get usage summary for today.

        Returns:
            UsageSummary for today's date
        """
        today_str = date.today().isoformat()
        return self._summarize(today_str, lambda r: r.timestamp[:10] == today_str)

    def get_monthly_summary(self, year: int, month: int) -> UsageSummary:
        """Get usage summary for a specific month.

        Args:
            year: Year (e.g. 2026)
            month: Month (1-12)

        Returns:
            UsageSummary for the specified month
        """
        prefix = f"{year}-{month:02d}"
        return self._summarize(prefix, lambda r: r.timestamp[:7] == prefix)

    def get_total_summary(self) -> UsageSummary:
        """Get all-time usage summary.

        Returns:
            UsageSummary across all recorded calls
        """
        return self._summarize("all-time", lambda _: True)

    def _summarize(
        self,
        period: str,
        predicate: Callable[[APICallRecord], bool],
    ) -> UsageSummary:
        """Build a summary from records matching the predicate."""
        records = self._read_records()
        summary = UsageSummary(period=period)

        for r in records:
            if predicate(r):
                summary.total_calls += 1
                summary.total_input_tokens += r.input_tokens
                summary.total_output_tokens += r.output_tokens
                summary.total_cost += r.estimated_cost
                summary.by_caller[r.caller] = (
                    summary.by_caller.get(r.caller, 0.0) + r.estimated_cost
                )

        summary.total_cost = round(summary.total_cost, 6)
        return summary


# Module-level singleton
_tracker: Optional[CostTracker] = None
_tracker_lock = threading.Lock()


def get_cost_tracker(usage_file: Optional[Path] = None) -> CostTracker:
    """Get the singleton CostTracker instance.

    Args:
        usage_file: Override the default usage file path.
                    Only used on first call (or if no singleton exists yet).

    Returns:
        CostTracker instance
    """
    global _tracker
    with _tracker_lock:
        if _tracker is None:
            _tracker = CostTracker(usage_file)
        return _tracker


def reset_tracker() -> None:
    """Reset the singleton (for testing)."""
    global _tracker
    with _tracker_lock:
        _tracker = None

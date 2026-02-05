"""In-app feedback capture — bugs and suggestions.

Captures user feedback (bugs, suggestions) to a local JSON file.
No external service needed. Jeff can review the file or it can
be sent with logs when debugging.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


class FeedbackType(str, Enum):
    BUG = "bug"
    SUGGESTION = "suggestion"


@dataclass
class FeedbackEntry:
    feedback_type: str
    description: str
    context: Optional[str] = None  # What the user was doing when it happened
    timestamp: Optional[str] = None


class FeedbackCapture:
    """Captures and stores user feedback locally.

    Feedback is appended to a JSON lines file (one entry per line)
    in the data directory. Simple, reliable, no external deps.
    """

    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._file_path = data_dir / "feedback.jsonl"

    def submit(
        self,
        feedback_type: FeedbackType,
        description: str,
        context: Optional[str] = None,
    ) -> FeedbackEntry:
        """Submit a feedback entry.

        Args:
            feedback_type: BUG or SUGGESTION
            description: What the user wants to report
            context: Optional context about what they were doing

        Returns:
            The saved FeedbackEntry
        """
        entry = FeedbackEntry(
            feedback_type=feedback_type.value,
            description=description,
            context=context,
            timestamp=datetime.now().isoformat(),
        )

        self._append(entry)

        logger.info(
            "Feedback captured",
            extra={
                "context": {
                    "type": feedback_type.value,
                    "description": description[:50],
                }
            },
        )

        return entry

    def get_all(self) -> list[FeedbackEntry]:
        """Read all feedback entries."""
        if not self._file_path.exists():
            return []

        entries: list[FeedbackEntry] = []
        try:
            for line in self._file_path.read_text(encoding="utf-8").strip().splitlines():
                if line.strip():
                    data = json.loads(line)
                    entries.append(
                        FeedbackEntry(
                            feedback_type=data["feedback_type"],
                            description=data["description"],
                            context=data.get("context"),
                            timestamp=data.get("timestamp"),
                        )
                    )
        except (OSError, json.JSONDecodeError):
            logger.warning("Failed to read feedback file", exc_info=True)

        return entries

    def count(self) -> int:
        """Count feedback entries."""
        return len(self.get_all())

    def _append(self, entry: FeedbackEntry) -> None:
        """Append entry to feedback file."""
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            with open(self._file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry)) + "\n")
        except OSError:
            logger.warning("Failed to write feedback", exc_info=True)

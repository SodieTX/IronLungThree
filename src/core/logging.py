"""Structured JSON logging for IronLung 3.

Provides consistent logging across all modules with:
    - JSON format for file logs
    - Human-readable console output
    - Rotating file handler
    - Context fields (prospect_id, company_id, etc.)

Usage:
    from src.core.logging import get_logger, setup_logging

    setup_logging()  # Call once at startup
    logger = get_logger(__name__)

    logger.info("Processing prospect", extra={"context": {"prospect_id": 123}})
"""

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime
from typing import Any, Optional


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for file output."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON.

        Args:
            record: The log record to format

        Returns:
            JSON string with timestamp, level, module, message, and context
        """
        log_data: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }

        # Add context if present
        if hasattr(record, "context"):
            log_data["context"] = record.context

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class ConsoleFormatter(logging.Formatter):
    """Human-readable format for console output."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record for console.

        Args:
            record: The log record to format

        Returns:
            Human-readable string
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        level = record.levelname[:4]
        message = record.getMessage()

        # Add context summary if present
        if hasattr(record, "context") and record.context:
            ctx_parts = [f"{k}={v}" for k, v in record.context.items()]
            if ctx_parts:
                message += f" [{', '.join(ctx_parts)}]"

        return f"{timestamp} {level:4s} {record.name}: {message}"


_logging_initialized = False


def setup_logging(
    log_dir: Optional[Path] = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> None:
    """Initialize logging system.

    Call once at application startup.

    Args:
        log_dir: Directory for log files. Defaults to ~/.ironlung/logs
        console_level: Minimum level for console output (default: INFO)
        file_level: Minimum level for file output (default: DEBUG)
    """
    global _logging_initialized

    if _logging_initialized:
        return

    # Determine log directory
    if log_dir is None:
        log_dir = Path.home() / ".ironlung" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Get root ironlung logger
    root_logger = logging.getLogger("ironlung")
    root_logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(ConsoleFormatter())
    root_logger.addHandler(console_handler)

    # File handler with rotation
    log_file = log_dir / "ironlung3.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)

    _logging_initialized = True
    root_logger.info("Logging initialized", extra={"context": {"log_dir": str(log_dir)}})


def get_logger(name: str) -> logging.Logger:
    """Get logger for module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance for the module
    """
    # Strip 'src.' prefix if present for cleaner names
    if name.startswith("src."):
        name = name[4:]
    return logging.getLogger(f"ironlung.{name}")

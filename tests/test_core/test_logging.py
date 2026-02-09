"""Tests for logging setup."""

import logging

import pytest

from src.core.logging import get_logger, setup_logging


class TestLogging:
    """Test logging configuration."""

    def test_get_logger_returns_logger(self):
        """get_logger returns a Logger instance."""
        logger = get_logger(__name__)
        assert isinstance(logger, logging.Logger)

    def test_get_logger_same_name_returns_same_logger(self):
        """Same name returns same logger instance."""
        logger1 = get_logger("test.module")
        logger2 = get_logger("test.module")
        assert logger1 is logger2

    def test_setup_logging_creates_handlers(self, tmp_path):
        """setup_logging creates file and console handlers."""
        import src.core.logging as log_module

        log_module._logging_initialized = False
        setup_logging(log_dir=tmp_path / "logs")
        root_logger = logging.getLogger("ironlung")
        assert len(root_logger.handlers) >= 2
        log_module._logging_initialized = False

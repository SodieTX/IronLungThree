"""Tests for logging setup."""

import pytest
import logging
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
    
    @pytest.mark.skip(reason="Stub not implemented")
    def test_setup_logging_creates_handlers(self, tmp_path):
        """setup_logging creates file and console handlers."""
        setup_logging(log_path=str(tmp_path / "logs"))
        # Verify handlers exist

"""Tests for exception hierarchy."""

import pytest

from src.core.exceptions import (
    ActiveCampaignError,
    BriaError,
    ConfigurationError,
    DatabaseError,
    DNCViolationError,
    ImportError_,
    IntegrationError,
    IronLungError,
    OutlookError,
    PipelineError,
    ValidationError,
)


class TestExceptionHierarchy:
    """Test exception inheritance."""

    def test_all_exceptions_inherit_from_ironlungerror(self):
        """All custom exceptions should inherit from IronLungError."""
        exceptions = [
            ConfigurationError,
            ValidationError,
            DatabaseError,
            IntegrationError,
            ImportError_,
            PipelineError,
        ]
        for exc_class in exceptions:
            assert issubclass(exc_class, IronLungError)

    def test_integration_errors_inherit_from_integrationerror(self):
        """Integration-specific errors inherit from IntegrationError."""
        exceptions = [OutlookError, BriaError, ActiveCampaignError]
        for exc_class in exceptions:
            assert issubclass(exc_class, IntegrationError)
            assert issubclass(exc_class, IronLungError)

    def test_dnc_violation_inherits_from_pipelineerror(self):
        """DNCViolationError inherits from PipelineError."""
        assert issubclass(DNCViolationError, PipelineError)
        assert issubclass(DNCViolationError, IronLungError)


class TestExceptionMessages:
    """Test exceptions can be raised with messages."""

    def test_ironlungerror_with_message(self):
        """IronLungError can have a message."""
        with pytest.raises(IronLungError, match="test error"):
            raise IronLungError("test error")

    def test_dnc_violation_with_message(self):
        """DNCViolationError can have detailed message."""
        msg = "Attempted to reactivate DNC prospect #123"
        with pytest.raises(DNCViolationError, match="reactivate"):
            raise DNCViolationError(msg)

    def test_catching_base_exception(self):
        """Can catch specific errors with base class."""
        try:
            raise OutlookError("OAuth failed")
        except IronLungError as e:
            assert "OAuth" in str(e)

"""IronLung 3 Exception Hierarchy.

All custom exceptions inherit from IronLungError.
DNCViolationError is its own class because DNC violations
are categorically different from other pipeline errors.

Exception Hierarchy:
    IronLungError (base)
    ├── ConfigurationError
    ├── ValidationError
    ├── DatabaseError
    ├── IntegrationError
    │   ├── OutlookError
    │   ├── BriaError
    │   └── ActiveCampaignError
    ├── ImportError_
    └── PipelineError
        └── DNCViolationError
"""


class IronLungError(Exception):
    """Base exception for all IronLung errors.

    All custom exceptions in IronLung 3 inherit from this class,
    allowing for broad exception handling when needed.
    """

    pass


class ConfigurationError(IronLungError):
    """Configuration is invalid or missing.

    Raised when:
        - Required environment variable is missing
        - Configuration file is malformed
        - Path is not writable
        - Credential validation fails
    """

    pass


class ValidationError(IronLungError):
    """Data validation failed.

    Raised when:
        - Required field is missing
        - Field value is invalid format
        - Business rule validation fails
    """

    pass


class DatabaseError(IronLungError):
    """Database operation failed.

    Raised when:
        - Database file cannot be opened
        - Database is locked
        - Query execution fails
        - Foreign key constraint violated
    """

    pass


class IntegrationError(IronLungError):
    """External integration failed.

    Base class for integration-specific errors.
    """

    pass


class OutlookError(IntegrationError):
    """Outlook/Microsoft Graph integration failed.

    Raised when:
        - OAuth authentication fails
        - Token refresh fails
        - API call fails
        - Email send fails
    """

    pass


class BriaError(IntegrationError):
    """Bria softphone integration failed.

    Raised when:
        - Bria is not installed
        - URI scheme fails to launch
        - Connection to Bria fails
    """

    pass


class ActiveCampaignError(IntegrationError):
    """ActiveCampaign API integration failed.

    Raised when:
        - API authentication fails
        - API call fails
        - Rate limit exceeded
    """

    pass


class ImportError_(IronLungError):
    """Import operation failed.

    Named with underscore to avoid shadowing builtin ImportError.

    Raised when:
        - File cannot be read
        - File format is invalid
        - Column mapping is incomplete
        - Parse error occurs
    """

    pass


class PipelineError(IronLungError):
    """Pipeline operation failed.

    Raised when:
        - Invalid population transition attempted
        - Business rule violation occurs
    """

    pass


class DNCViolationError(PipelineError):
    """Attempted operation on DNC record.

    This exception is NEVER swallowed. It indicates an attempt to:
        - Transition FROM a DNC record
        - Merge data into a DNC record
        - Reactivate a DNC record

    DNC (Do Not Contact) is permanent, absolute, sacrosanct.
    This exception type exists separately because DNC violations
    are categorically different from other pipeline errors.
    """

    pass

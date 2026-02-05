"""Core package - Configuration, logging, exceptions.

This package provides foundational infrastructure used by all other layers.

Modules:
    - config: Environment and configuration management
    - logging: Structured JSON logging
    - exceptions: Custom exception hierarchy
    - tasks: Thread and task management
"""

from src.core.exceptions import (
    IronLungError,
    ConfigurationError,
    ValidationError,
    DatabaseError,
    IntegrationError,
    ImportError_,
    PipelineError,
    DNCViolationError,
)

__all__ = [
    "IronLungError",
    "ConfigurationError",
    "ValidationError",
    "DatabaseError",
    "IntegrationError",
    "ImportError_",
    "PipelineError",
    "DNCViolationError",
]

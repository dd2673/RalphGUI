"""
Ralph GUI Library - Cross-platform utility functions

This package provides Python implementations of core Ralph utilities
for timeout handling, date formatting, log management, and file protection.
"""

from .timeout_utils import portable_timeout, TimeoutExpired
from .date_utils import (
    get_iso_timestamp,
    get_basic_timestamp,
    get_epoch_seconds,
    parse_iso_to_epoch,
)
from .log_utils import rotate_logs
from .file_protection import (
    RALPH_REQUIRED_PATHS,
    validate_ralph_integrity,
    get_integrity_report,
)

__all__ = [
    # timeout_utils
    "portable_timeout",
    "TimeoutExpired",
    # date_utils
    "get_iso_timestamp",
    "get_basic_timestamp",
    "get_epoch_seconds",
    "parse_iso_to_epoch",
    # log_utils
    "rotate_logs",
    # file_protection
    "RALPH_REQUIRED_PATHS",
    "validate_ralph_integrity",
    "get_integrity_report",
]

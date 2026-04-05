"""
date_utils.py - Cross-platform date utility functions
Provides consistent date formatting and arithmetic across systems
"""
from datetime import datetime, timezone, timedelta
from typing import Optional


def get_iso_timestamp() -> str:
    """Get current timestamp in ISO 8601 format with seconds precision.

    Returns: YYYY-MM-DDTHH:MM:SS+00:00 format
    """
    return datetime.now(timezone.utc).isoformat()


def get_next_hour_time() -> str:
    """Get time component (HH:MM:SS) for one hour from now.

    Returns: HH:MM:SS format
    """
    now = datetime.now(timezone.utc)
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return next_hour.strftime("%H:%M:%S")


def get_basic_timestamp() -> str:
    """Get current timestamp in basic format.

    Returns: YYYY-MM-DD HH:MM:SS format
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_epoch_seconds() -> int:
    """Get current Unix epoch time in seconds.

    Returns: Integer seconds since 1970-01-01 00:00:00 UTC
    """
    return int(datetime.now(timezone.utc).timestamp())


def parse_iso_to_epoch(iso_timestamp: Optional[str]) -> int:
    """Convert ISO 8601 timestamp to Unix epoch seconds.

    Args:
        iso_timestamp: ISO timestamp (e.g., "2025-01-15T10:30:00+00:00")

    Returns:
        Unix epoch seconds

    Falls back to current epoch on parse failure (safe default).
    """
    if not iso_timestamp or iso_timestamp == "null":
        return get_epoch_seconds()

    try:
        # Handle various ISO formats
        # Remove trailing 'Z' and replace with +00:00
        ts = iso_timestamp.replace('Z', '+00:00')

        # Try to parse the timestamp
        dt = datetime.fromisoformat(ts)
        return int(dt.timestamp())
    except (ValueError, TypeError):
        # Fallback: manual parsing for basic ISO format
        try:
            # Basic format: YYYY-MM-DDTHH:MM:SS
            basic_ts = iso_timestamp.split('+')[0].split('Z')[0]
            dt = datetime.fromisoformat(basic_ts)
            return int(dt.timestamp())
        except (ValueError, TypeError):
            # Ultimate fallback: return current epoch
            return get_epoch_seconds()

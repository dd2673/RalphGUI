"""
date_utils.py - Cross-platform date utility functions

Provides consistent date formatting and arithmetic across Windows, Linux, and macOS.
"""

import datetime
import time
from typing import Optional


def get_iso_timestamp() -> str:
    """Get current timestamp in ISO 8601 format with timezone.

    Returns:
        str: Timestamp in YYYY-MM-DDTHH:MM:SS+00:00 format.

    Example:
        >>> get_iso_timestamp()
        '2025-01-15T10:30:00+00:00'
    """
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")


def get_basic_timestamp() -> str:
    """Get current timestamp in basic format.

    Returns:
        str: Timestamp in YYYY-MM-DD HH:MM:SS format (local time).

    Example:
        >>> get_basic_timestamp()
        '2025-01-15 10:30:00'
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_epoch_seconds() -> int:
    """Get current Unix epoch time in seconds.

    Returns:
        int: Seconds since 1970-01-01 00:00:00 UTC.

    Example:
        >>> get_epoch_seconds()  # doctest: +SKIP
        1705315800
    """
    return int(time.time())


def parse_iso_to_epoch(iso_timestamp: Optional[str]) -> int:
    """Convert ISO 8601 timestamp to Unix epoch seconds.

    Args:
        iso_timestamp: ISO timestamp string (e.g., "2025-01-15T10:30:00+00:00").
                      If None or "null", returns current epoch.

    Returns:
        int: Unix epoch seconds.

    Example:
        >>> parse_iso_to_epoch("2025-01-15T10:30:00+00:00")  # doctest: +SKIP
        1705315800
    """
    if not iso_timestamp or iso_timestamp == "null":
        return get_epoch_seconds()

    try:
        # Handle various ISO 8601 formats
        # Remove colons from timezone if present (e.g., +00:00 -> +0000)
        ts = iso_timestamp
        if isinstance(ts, str):
            # Handle Z suffix (UTC)
            if ts.endswith("Z"):
                ts = ts[:-1] + "+0000"
            # Handle +HH:MM format
            elif len(ts) > 25 and ts[22] == ":":
                ts = ts[:22] + ts[23:25] + ts[26:]

        # Parse the timestamp
        if "+" in ts:
            base, tz = ts.rsplit("+", 1)
            dt = datetime.datetime.fromisoformat(base)
            # Convert to epoch
            return int(dt.timestamp()) - (int(tz[:2]) * 3600 + int(tz[2:4]) * 60)
        elif "-" in ts[:25]:
            base, tz = ts.rsplit("-", 1)
            dt = datetime.datetime.fromisoformat(base)
            return int(dt.timestamp()) + (int(tz[:2]) * 3600 + int(tz[2:4]) * 60)
        else:
            dt = datetime.datetime.fromisoformat(ts)
            return int(dt.timestamp())
    except (ValueError, TypeError):
        # Fallback: try basic parsing
        try:
            # Parse YYYY-MM-DDTHH:MM:SS
            parts = iso_timestamp.split("T")
            if len(parts) == 2:
                date_part, time_part = parts
                date_components = date_part.split("-")
                time_components = time_part.replace(":", "")[:6].split(":")

                if len(date_components) >= 3 and len(time_components) >= 3:
                    year, month, day = int(date_components[0]), int(date_components[1]), int(date_components[2])
                    hour, minute, second = int(time_components[0]), int(time_components[1]), int(time_components[2])
                    dt = datetime.datetime(year, month, day, hour, minute, second)
                    return int(dt.timestamp())
        except (ValueError, TypeError, IndexError):
            pass

    # Ultimate fallback: return current epoch
    return get_epoch_seconds()

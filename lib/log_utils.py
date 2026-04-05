"""
log_utils.py - Log management utilities

Provides log rotation functionality for Ralph projects.
Cross-platform file size checking using os.path.getsize().
"""

import os
import shutil
from typing import Optional


def rotate_logs(log_file: str, max_size_mb: float = 10.0, keep_count: int = 4) -> bool:
    """Rotate log files when they exceed a maximum size.

    Keeps `keep_count` archived files (log_file.1 through log_file.N).
    The oldest archive is deleted to make room for new rotations.

    Args:
        log_file: Path to the log file to rotate.
        max_size_mb: Maximum size in MB before rotation (default: 10MB).
        keep_count: Number of archived files to keep (default: 4).

    Returns:
        bool: True if rotation occurred, False otherwise.

    Example:
        >>> rotate_logs("/var/log/ralph.log")
        True
        >>> rotate_logs("/var/log/ralph.log", max_size_mb=5.0, keep_count=3)
        True
    """
    if not os.path.exists(log_file):
        return False

    max_size_bytes = int(max_size_mb * 1024 * 1024)

    try:
        file_size = os.path.getsize(log_file)
    except OSError:
        return False

    if file_size < max_size_bytes:
        return False

    # Rotate: delete oldest, shift others up
    # Remove the oldest archive first
    oldest_archive = f"{log_file}.{keep_count}"
    if os.path.exists(oldest_archive):
        try:
            os.remove(oldest_archive)
        except OSError:
            pass

    # Shift remaining archives
    for i in range(keep_count - 1, 0, -1):
        current_archive = f"{log_file}.{i}"
        next_archive = f"{log_file}.{i + 1}"
        if os.path.exists(current_archive):
            try:
                shutil.move(current_archive, next_archive)
            except OSError:
                pass

    # Move current log file to .1
    try:
        shutil.move(log_file, f"{log_file}.1")
    except OSError:
        return False

    return True

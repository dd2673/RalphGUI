"""
timeout_utils.py - Cross-platform timeout utility functions
Provides consistent timeout command execution across systems

On Windows: Uses Python's subprocess with timeout parameter
On Unix: Uses the standard timeout command
"""
import subprocess
import sys
import shutil
from typing import List, Optional, Union


# Cached timeout command to avoid repeated detection
_cached_timeout_cmd: Optional[str] = None


def detect_timeout_command() -> Optional[str]:
    """Detect the available timeout command for this platform.

    Returns:
        The timeout command path or None if not available
    """
    global _cached_timeout_cmd

    if _cached_timeout_cmd is not None:
        return _cached_timeout_cmd

    if sys.platform == "win32":
        # Windows: Python's subprocess handles timeouts natively
        _cached_timeout_cmd = "python"
    else:
        # Unix: try standard timeout command
        timeout_path = shutil.which("timeout")
        if timeout_path:
            _cached_timeout_cmd = timeout_path
        else:
            _cached_timeout_cmd = None

    return _cached_timeout_cmd


def has_timeout_command() -> bool:
    """Check if a timeout command is available on this system.

    Returns:
        True if available, False if not
    """
    return detect_timeout_command() is not None


def get_timeout_status_message() -> str:
    """Get a user-friendly message about timeout availability.

    Returns:
        Status message string
    """
    cmd = detect_timeout_command()

    if cmd:
        return f"Timeout command available: {cmd}"

    if sys.platform == "darwin":
        return "Timeout command not found. Install GNU coreutils: brew install coreutils"
    elif sys.platform == "win32":
        return "Timeout handled natively by Python subprocess"
    else:
        return "Timeout command not found. Install coreutils: sudo apt-get install coreutils"


def portable_timeout(
    duration: Union[int, float],
    *args: str,
    **kwargs
) -> int:
    """Execute a command with a timeout (cross-platform).

    Args:
        duration: Timeout duration in seconds
        *args: Command and arguments to execute
        **kwargs: Additional arguments for subprocess

    Returns:
        0 if command completed successfully within timeout
        124 if command timed out (GNU timeout behavior)
        Exit code from the executed command on other errors

    Raises:
        ValueError: If duration or command is not provided
    """
    if duration is None or duration <= 0:
        raise ValueError("portable_timeout requires a positive duration")

    if not args:
        raise ValueError("portable_timeout requires a command to execute")

    timeout_cmd = detect_timeout_command()

    if timeout_cmd is None:
        raise RuntimeError(
            "No timeout command available on this system. "
            "On Windows, use Python's subprocess timeout parameter instead."
        )

    if timeout_cmd == "python":
        # Windows/native Python: use subprocess timeout directly
        try:
            result = subprocess.run(
                list(args),
                timeout=duration,
                **kwargs
            )
            return result.returncode
        except subprocess.TimeoutExpired:
            return 124
    else:
        # Unix: use timeout command
        try:
            result = subprocess.run(
                [timeout_cmd, str(duration)] + list(args),
                **kwargs
            )
            return result.returncode
        except subprocess.TimeoutExpired:
            return 124


def reset_timeout_detection() -> None:
    """Reset the cached timeout command (useful for testing)."""
    global _cached_timeout_cmd
    _cached_timeout_cmd = None

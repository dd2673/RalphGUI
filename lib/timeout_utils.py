"""
timeout_utils.py - Cross-platform timeout execution

Provides consistent timeout command execution across Windows, Linux, and macOS.
Uses threading on Windows (via taskkill) and signal-based timeout on Unix.
"""

import subprocess
import threading
import sys
import os
from typing import List, Any, Optional


class TimeoutExpired(Exception):
    """Exception raised when a command times out."""

    def __init__(self, cmd: List[str], seconds: float):
        self.cmd = cmd
        self.seconds = seconds
        super().__init__(f"Command timed out after {seconds} seconds: {' '.join(cmd)}")


def portable_timeout(seconds: float, cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Execute a command with a timeout (cross-platform).

    Args:
        seconds: Timeout duration in seconds.
        cmd: Command and arguments as a list.
        **kwargs: Additional arguments passed to subprocess.run().

    Returns:
        subprocess.CompletedProcess: The completed process result.

    Raises:
        TimeoutExpired: If the command times out.
        subprocess.SubprocessError: If the command fails to start.

    Example:
        >>> result = portable_timeout(30.0, ["curl", "-s", "https://example.com"])
        >>> print(result.stdout)
    """
    if sys.platform == "win32":
        return _windows_timeout(seconds, cmd, **kwargs)
    else:
        return _unix_timeout(seconds, cmd, **kwargs)


def _windows_timeout(seconds: float, cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Windows implementation using threading and taskkill.

    Args:
        seconds: Timeout duration in seconds.
        cmd: Command and arguments as a list.
        **kwargs: Additional arguments passed to subprocess.run().

    Returns:
        subprocess.CompletedProcess: The completed process result.

    Raises:
        TimeoutExpired: If the command times out.
    """
    result_container: List[Optional[subprocess.CompletedProcess]] = [None]
    exception_container: List[Optional[Exception]] = [None]
    process_ref: List[Optional[subprocess.Popen]] = [None]

    def target():
        try:
            process_ref[0] = subprocess.Popen(cmd, **kwargs)
            result_container[0] = process_ref[0].wait()
        except Exception as e:  # pylint: disable=broad-except
            exception_container[0] = e

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout=seconds)

    if thread.is_alive():
        # Process still running, kill it
        if process_ref[0] is not None and process_ref[0].poll() is None:
            try:
                # Use taskkill to kill the process tree
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(process_ref[0].pid)],
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass  # Best effort kill

        thread.join(timeout=5)  # Wait for thread to finish
        raise TimeoutExpired(cmd, seconds)

    if exception_container[0] is not None:
        raise exception_container[0]

    # Return a CompletedProcess-like object
    # Since we only got the return code from wait(), we need to reconstruct
    completed = subprocess.CompletedProcess(args=cmd, returncode=result_container[0] or 0)
    return completed


def _unix_timeout(seconds: float, cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Unix implementation using SIGALRM signal.

    Args:
        seconds: Timeout duration in seconds.
        cmd: Command and arguments as a list.
        **kwargs: Additional arguments passed to subprocess.run().

    Returns:
        subprocess.CompletedProcess: The completed process result.

    Raises:
        TimeoutExpired: If the command times out.
    """
    import signal

    def raise_timeout(signum, frame):
        raise TimeoutExpired(cmd, seconds)

    old_handler = signal.signal(signal.SIGALRM, raise_timeout)
    signal.alarm(int(seconds))

    try:
        result = subprocess.run(cmd, **kwargs)
        return result
    except TimeoutExpired:
        raise
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

"""
file_protection.py - File integrity validation for Ralph projects

Validates that critical Ralph configuration files exist before loop execution.
Cross-platform implementation without Unix-specific commands.
"""

import os
from typing import List, Optional, Tuple

# Required paths for a functioning Ralph project
# Only includes files critical for the loop to run - not optional state files
RALPH_REQUIRED_PATHS: List[str] = [
    ".ralph",
    ".ralph/PROMPT.md",
    ".ralph/fix_plan.md",
    ".ralph/AGENT.md",
    ".ralphrc",
]

# Tracks missing files after validation (populated by validate_ralph_integrity)
RALPH_MISSING_FILES: List[str] = []


def validate_ralph_integrity(base_dir: Optional[str] = None) -> bool:
    """Validate that all required Ralph files and directories exist.

    Args:
        base_dir: Base directory to check from (default: current working directory).

    Returns:
        bool: True if all required paths exist, False otherwise.

    Example:
        >>> validate_ralph_integrity()
        True
        >>> validate_ralph_integrity("/path/to/project")
        False
    """
    global RALPH_MISSING_FILES

    RALPH_MISSING_FILES = []

    if base_dir is None:
        base_dir = os.getcwd()

    for path in RALPH_REQUIRED_PATHS:
        full_path = os.path.join(base_dir, path) if not os.path.isabs(path) else path
        if not os.path.exists(full_path):
            RALPH_MISSING_FILES.append(path)

    return len(RALPH_MISSING_FILES) == 0


def get_integrity_report() -> str:
    """Generate a human-readable integrity report.

    Must be called after validate_ralph_integrity.

    Returns:
        str: Human-readable report with missing files and recovery instructions.

    Example:
        >>> validate_ralph_integrity()
        True
        >>> print(get_integrity_report())
        All required Ralph files are intact.
    """
    if len(RALPH_MISSING_FILES) == 0:
        return "All required Ralph files are intact."

    lines = ["Ralph integrity check failed. Missing files:"]
    for path in RALPH_MISSING_FILES:
        lines.append(f"  - {path}")
    lines.append("")
    lines.append("To restore, run: ralph-enable --force")

    return "\n".join(lines)

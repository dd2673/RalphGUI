"""
file_protection.py - File integrity validation for Ralph projects
Validates that critical Ralph configuration files exist before loop execution
"""
from pathlib import Path
from typing import List, Tuple

# Required paths for a functioning Ralph project
# Only includes files critical for the loop to run — not optional state files
RALPH_REQUIRED_PATHS = [
    ".ralph",
    ".ralph/PROMPT.md",
    ".ralph/fix_plan.md",
    ".ralph/AGENT.md",
    ".ralphrc",
]


def validate_ralph_integrity(project_dir: Path) -> Tuple[bool, List[str]]:
    """Validate that all required Ralph files and directories exist.

    Args:
        project_dir: Path to the project directory

    Returns:
        Tuple of (all_valid, missing_files)
        - all_valid: True if all required paths exist
        - missing_files: List of missing item paths
    """
    missing_files: List[str] = []

    for path_str in RALPH_REQUIRED_PATHS:
        path = project_dir / path_str
        if not path.exists():
            missing_files.append(path_str)

    return len(missing_files) == 0, missing_files


def get_integrity_report(project_dir: Path) -> str:
    """Generate a human-readable integrity report.

    Args:
        project_dir: Path to the project directory

    Returns:
        Report text string
    """
    all_valid, missing_files = validate_ralph_integrity(project_dir)

    if all_valid:
        return "All required Ralph files are intact."

    lines = ["Ralph integrity check failed. Missing files:"]
    for path in missing_files:
        lines.append(f"  - {path}")
    lines.append("")
    lines.append("To restore, run: ralph-enable --force")

    return "\n".join(lines)

#!/usr/bin/env python3
"""
task_sources.py - Task import utilities for Ralph GUI
Supports importing tasks from beads, GitHub Issues, and PRD files
"""

import subprocess
import json
import re
import shutil
from pathlib import Path
from typing import Optional


# =============================================================================
# BEADS INTEGRATION
# =============================================================================

def check_beads_available() -> bool:
    """
    Check if beads (bd) is available and configured.

    Returns:
        True if beads is available, False otherwise.
    """
    # Check for .beads directory in current working directory
    if not Path(".beads").is_dir():
        return False

    # Check if bd command exists
    if not shutil.which("bd"):
        return False

    return True


def fetch_beads_tasks(filter_status: str = "open") -> str:
    """
    Fetch tasks from beads issue tracker.

    Args:
        filter_status: Status filter - "open", "in_progress", or "all" (default: "open")

    Returns:
        Tasks in markdown checkbox format, one per line.
        e.g., "- [ ] [issue-001] Fix authentication bug"
        Returns empty string if no tasks found or on error.
    """
    if not check_beads_available():
        return ""

    tasks = ""

    # Build bd list command arguments
    bd_args = ["list"]
    if filter_status == "open":
        bd_args.extend(["--status", "open"])
    elif filter_status == "in_progress":
        bd_args.extend(["--status", "in_progress"])
    elif filter_status == "all":
        bd_args.append("--all")

    # Try to get tasks as JSON
    try:
        result = subprocess.run(
            ["bd"] + bd_args + ["--json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        json_output = result.stdout

        if json_output and shutil.which("jq"):
            # Parse JSON and format as markdown tasks
            try:
                proc = subprocess.run(
                    ["jq", "-r",
                     '.[] | select(.status == "closed" | not) | select((.id // "") != "" and (.title // "") != "") | "- [ ] [" + .id + "] " + .title'],
                    input=json_output,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    tasks = proc.stdout.strip()
            except Exception:
                pass
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass

    # Fallback: try plain text output if JSON failed or produced no results
    if not tasks:
        fallback_args = ["list"]
        if filter_status == "open":
            fallback_args.extend(["--status", "open"])
        elif filter_status == "in_progress":
            fallback_args.extend(["--status", "in_progress"])
        elif filter_status == "all":
            fallback_args.append("--all")

        try:
            result = subprocess.run(
                ["bd"] + fallback_args,
                capture_output=True,
                text=True,
                timeout=30
            )
            lines = result.stdout.splitlines()
            for line in lines:
                # Extract ID and title from bd list output
                # Format: "○ cnzb-xxx [● P2] [task] - Title here"
                id_match = re.search(r'[a-z]+-[a-z0-9]+', line)
                if id_match:
                    task_id = id_match.group(0)
                    # Extract title after the last " - " separator
                    if " - " in line:
                        title = line.rsplit(" - ", 1)[-1].strip()
                    else:
                        title = line
                    if task_id and title:
                        tasks += f"- [ ] [{task_id}] {title}\n"
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass

    return tasks.strip()


def get_beads_count() -> int:
    """
    Get count of open beads issues.

    Returns:
        Number of open beads issues, 0 if unavailable.
    """
    if not check_beads_available():
        return 0

    try:
        result = subprocess.run(
            ["bd", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        json_output = result.stdout

        if json_output and shutil.which("jq"):
            try:
                proc = subprocess.run(
                    ["jq", "[.[] | select(.status == \"closed\" | not)] | length"],
                    input=json_output,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    return int(proc.stdout.strip())
            except (ValueError, Exception):
                pass

        # Fallback: count lines
        result = subprocess.run(
            ["bd", "list"],
            capture_output=True,
            text=True,
            timeout=30
        )
        return len([l for l in result.stdout.splitlines() if l.strip()])
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return 0


# =============================================================================
# GITHUB ISSUES INTEGRATION
# =============================================================================

def check_github_available() -> bool:
    """
    Check if GitHub CLI (gh) is available and authenticated.

    Returns:
        True if GitHub is available and authenticated, False otherwise.
    """
    # Check for gh command
    if not shutil.which("gh"):
        return False

    # Check if authenticated
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False

    # Check if in a git repo with GitHub remote
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if "github.com" not in result.stdout:
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False

    return True


def fetch_github_tasks(label: Optional[str] = None, limit: int = 50) -> str:
    """
    Fetch issues from GitHub.

    Args:
        label: Label to filter by (optional, default: None)
        limit: Maximum number of issues (optional, default: 50)

    Returns:
        Tasks in markdown checkbox format.
        e.g., "- [ ] [#123] Implement user authentication"
        Returns empty string on error.
    """
    if not check_github_available():
        return ""

    # Build gh command
    gh_args = ["issue", "list", "--state", "open", "--limit", str(limit), "--json", "number,title,labels"]
    if label:
        gh_args.extend(["--label", label])

    # Fetch issues
    try:
        result = subprocess.run(
            ["gh"] + gh_args,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            return ""

        json_output = result.stdout

        if not json_output:
            return ""

        # Parse JSON
        try:
            issues = json.loads(json_output)
            tasks = ""
            for issue in issues:
                tasks += f"- [ ] [#{issue['number']}] {issue['title']}\n"
            return tasks.strip()
        except json.JSONDecodeError:
            pass

        # Fallback: use jq if available
        if shutil.which("jq"):
            try:
                proc = subprocess.run(
                    ["jq", "-r", '.[] | "- [ ] [#" + (.number | tostring) + "] " + .title'],
                    input=json_output,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if proc.returncode == 0:
                    return proc.stdout.strip()
            except Exception:
                pass

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass

    return ""


def get_github_issue_count(label: Optional[str] = None) -> int:
    """
    Get count of open GitHub issues.

    Args:
        label: Label to filter by (optional)

    Returns:
        Number of open issues, 0 if GitHub unavailable.
    """
    if not check_github_available():
        return 0

    gh_args = ["issue", "list", "--state", "open", "--json", "number"]
    if label:
        gh_args.extend(["--label", label])

    try:
        result = subprocess.run(
            ["gh"] + gh_args,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            return 0

        json_output = result.stdout

        if json_output and shutil.which("jq"):
            try:
                proc = subprocess.run(
                    ["jq", "length"],
                    input=json_output,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    return int(proc.stdout.strip())
            except (ValueError, Exception):
                pass

        # Fallback: count lines
        result = subprocess.run(
            ["gh", "issue", "list", "--state", "open"],
            capture_output=True,
            text=True,
            timeout=30
        )
        return len([l for l in result.stdout.splitlines() if l.strip()])
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return 0


def get_github_labels() -> str:
    """
    Get available labels from GitHub repo.

    Returns:
        Newline-separated list of label names.
        Returns empty string if unavailable.
    """
    if not check_github_available():
        return ""

    try:
        result = subprocess.run(
            ["gh", "label", "list", "--json", "name", "--jq", ".[].name"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass

    return ""


# =============================================================================
# PRD CONVERSION
# =============================================================================

def extract_prd_tasks(prd_file: str) -> str:
    """
    Extract tasks from a PRD/specification document.

    Args:
        prd_file: Path to the PRD file

    Returns:
        Tasks in markdown checkbox format.
        Returns empty string if file not found or no tasks.
    """
    path = Path(prd_file)

    if not path.is_file():
        return ""

    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        try:
            content = path.read_text(encoding="latin-1")
        except OSError:
            return ""

    tasks = ""
    lines = content.splitlines()

    # Look for existing checkbox items
    checkbox_pattern = re.compile(r'^[\s]*[-*][\s]*\[[\s]*[xX ]?[\s]*\]')
    for line in lines:
        if checkbox_pattern.match(line):
            # Normalize to unchecked format
            normalized = re.sub(r'\[x\]', '[ ]', line, flags=re.IGNORECASE)
            normalized = re.sub(r'\[X\]', '[ ]', normalized)
            tasks += normalized.strip() + "\n"

    # Look for numbered list items that look like tasks
    numbered_pattern = re.compile(r'^[\s]*[0-9]+\.[\s]+')
    for line in lines:
        if numbered_pattern.match(line):
            # Convert numbered item to checkbox
            task_text = re.sub(r'^[\s]*[0-9]*\.[\s]*', '', line)
            if task_text.strip():
                tasks += f"- [ ] {task_text.strip()}\n"

    # Look for headings that might be task sections (informational only)
    heading_pattern = re.compile(r'^#{1,3}[\s]+(TODO|Tasks|Requirements|Features|Backlog|Sprint)',
                                 re.IGNORECASE)
    for line in lines:
        if heading_pattern.match(line):
            # This is informational - actual task extraction would need more context
            pass

    # Clean up and output (limit to 30 tasks)
    if tasks:
        unique_tasks = []
        seen = set()
        for task in tasks.splitlines():
            if task.strip() and task not in seen:
                seen.add(task)
                unique_tasks.append(task)
                if len(unique_tasks) >= 30:
                    break
        return "\n".join(unique_tasks)

    return ""


def convert_prd_with_claude(prd_file: str, output_dir: str = ".ralph") -> bool:
    """
    Full PRD conversion using Claude (calls ralph-import logic).

    Args:
        prd_file: Path to the PRD file
        output_dir: Directory to output converted files (optional, defaults to .ralph/)

    Returns:
        True if full conversion was done, False for basic extraction.
    """
    path = Path(prd_file)

    if not path.is_file():
        return False

    # Check if ralph-import is available for full conversion
    if shutil.which("ralph-import"):
        # Use ralph-import for full conversion
        # Note: ralph-import creates a new project, so we need to adapt
        return False

    # Fall back to basic extraction
    extract_prd_tasks(prd_file)
    return False


# =============================================================================
# TASK NORMALIZATION
# =============================================================================

def normalize_tasks(tasks: str, source: str = "unknown") -> str:
    """
    Normalize tasks to consistent markdown format.

    Args:
        tasks: Raw task text (multi-line)
        source: Source identifier (beads, github, prd)

    Returns:
        Normalized tasks in markdown checkbox format.
    """
    if not tasks:
        return ""

    normalized = []
    checkbox_pattern = re.compile(r'^[\s]*-[\s]*\[[\s]*[xX ]?[\s]*\]')
    bullet_pattern = re.compile(r'^[\s]*[-*][\s]+')
    numbered_pattern = re.compile(r'^[\s]*[0-9]+\.?[\s]+')

    for line in tasks.splitlines():
        line = line.strip()
        if not line:
            continue

        # Already in checkbox format
        if checkbox_pattern.match(line):
            # Normalize the checkbox
            normalized_line = re.sub(r'\[x\]', '[ ]', line, flags=re.IGNORECASE)
            normalized_line = re.sub(r'\[X\]', '[ ]', normalized_line)
            normalized.append(normalized_line)
            continue

        # Bullet point without checkbox
        if bullet_pattern.match(line):
            text = re.sub(r'^[\s]*[-*][\s]*', '', line)
            normalized.append(f"- [ ] {text}")
            continue

        # Numbered item
        if numbered_pattern.match(line):
            text = re.sub(r'^[\s]*[0-9]*\.?[\s]*', '', line)
            normalized.append(f"- [ ] {text}")
            continue

        # Plain text line - make it a task
        normalized.append(f"- [ ] {line}")

    return "\n".join(normalized)


def prioritize_tasks(tasks: str) -> str:
    """
    Sort tasks by priority heuristics.

    Args:
        tasks: Tasks in markdown format

    Returns:
        Tasks sorted with priority indicators.
    """
    if not tasks:
        return ""

    high_priority = []
    medium_priority = []
    low_priority = []

    high_patterns = [
        r'critical', r'urgent', r'blocker', r'breaking', r'security',
        r'\bp0\b', r'\bp1\b'
    ]
    low_patterns = [
        r'nice\.to\.have', r'optional', r'future', r'later',
        r'\bp3\b', r'\bp4\b', r'low\.priority'
    ]
    important_patterns = [
        r'important', r'should', r'must', r'needed', r'required',
        r'\bp2\b'
    ]

    for line in tasks.splitlines():
        line_lower = line.lower()

        # Check for priority indicators
        if any(re.search(p, line_lower) for p in high_patterns):
            high_priority.append(line)
        elif any(re.search(p, line_lower) for p in low_patterns):
            low_priority.append(line)
        elif any(re.search(p, line_lower) for p in important_patterns):
            high_priority.append(line)
        else:
            medium_priority.append(line)

    # Build output
    output_parts = []

    if high_priority:
        output_parts.append("## High Priority")
        output_parts.extend(high_priority)
        output_parts.append("")

    if medium_priority:
        output_parts.append("## Medium Priority")
        output_parts.extend(medium_priority)
        output_parts.append("")

    if low_priority:
        output_parts.append("## Low Priority")
        output_parts.extend(low_priority)

    return "\n".join(output_parts).strip()


# =============================================================================
# COMBINED IMPORT
# =============================================================================

def import_tasks_from_sources(
    sources: str,
    prd_file: Optional[str] = None,
    github_label: Optional[str] = None
) -> str:
    """
    Import tasks from multiple sources.

    Args:
        sources: Space-separated list of sources: "beads", "github", "prd"
        prd_file: Path to PRD file (required if "prd" in sources)
        github_label: GitHub label filter (optional)

    Returns:
        Combined tasks in markdown format.
        Returns empty string if no tasks imported.
    """
    sources_list = sources.lower().split()
    all_tasks = ""
    source_count = 0

    # Import from beads
    if "beads" in sources_list:
        beads_tasks = fetch_beads_tasks()
        if beads_tasks:
            all_tasks += "\n# Tasks from beads\n"
            all_tasks += beads_tasks + "\n"
            source_count += 1

    # Import from GitHub
    if "github" in sources_list:
        github_tasks = fetch_github_tasks(github_label)
        if github_tasks:
            all_tasks += "\n# Tasks from GitHub\n"
            all_tasks += github_tasks + "\n"
            source_count += 1

    # Import from PRD
    if "prd" in sources_list:
        if prd_file and Path(prd_file).is_file():
            prd_tasks = extract_prd_tasks(prd_file)
            if prd_tasks:
                all_tasks += "\n# Tasks from PRD\n"
                all_tasks += prd_tasks + "\n"
                source_count += 1

    if not all_tasks:
        return ""

    # Normalize and output
    return normalize_tasks(all_tasks, "combined")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Task import utilities for Ralph GUI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # beads subcommand
    beads_parser = subparsers.add_parser("beads", help="Beads integration")
    beads_parser.add_argument("--status", choices=["open", "in_progress", "all"],
                              default="open", help="Filter status")

    # github subcommand
    github_parser = subparsers.add_parser("github", help="GitHub integration")
    github_parser.add_argument("--label", help="Label filter")
    github_parser.add_argument("--limit", type=int, default=50, help="Max issues")

    # prd subcommand
    prd_parser = subparsers.add_parser("prd", help="PRD extraction")
    prd_parser.add_argument("file", help="PRD file path")

    # import subcommand
    import_parser = subparsers.add_parser("import", help="Import from multiple sources")
    import_parser.add_argument("--sources", required=True,
                               help="Space-separated list: beads github prd")
    import_parser.add_argument("--prd", help="PRD file path")
    import_parser.add_argument("--github-label", help="GitHub label")

    args = parser.parse_args()

    if args.command == "beads":
        if check_beads_available():
            print(fetch_beads_tasks(args.status))
        else:
            print("Beads not available", file=__import__('sys').stderr)
    elif args.command == "github":
        if check_github_available():
            print(fetch_github_tasks(args.label, args.limit))
        else:
            print("GitHub not available", file=__import__('sys').stderr)
    elif args.command == "prd":
        result = extract_prd_tasks(args.file)
        print(result)
    elif args.command == "import":
        result = import_tasks_from_sources(args.sources, args.prd, args.github_label)
        print(result)
    else:
        parser.print_help()

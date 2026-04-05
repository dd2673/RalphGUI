#!/usr/bin/env python3
"""
task_sources.py - Task import utilities for Ralph enable

Supports importing tasks from:
- Beads issue tracker (bd command)
- GitHub Issues (gh CLI)
- PRD/specification documents
"""

import os
import re
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Priority keywords for task prioritization
HIGH_PRIORITY = ["critical", "urgent", "blocker", "breaking", "security", "p0", "p1"]
LOW_PRIORITY = ["nice to have", "optional", "future", "later", "p3", "p4"]


def check_beads_available() -> bool:
    """
    Check if beads (bd) is available and configured.

    Returns:
        True if .beads directory exists and bd command is available.
    """
    # Check for .beads directory
    if not os.path.isdir(".beads"):
        return False

    # Check if bd command exists
    try:
        result = subprocess.run(
            ["bd", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def fetch_beads_tasks(
    beads_dir: str = ".beads",
    filter_status: str = "open"
) -> List[Dict]:
    """
    Fetch tasks from beads issue tracker.

    Args:
        beads_dir: Path to .beads directory (default: ".beads")
        filter_status: Status filter - "open", "in_progress", or "all" (default: "open")

    Returns:
        List of task dictionaries with 'id', 'title', 'status' fields.
    """
    if not check_beads_available():
        return []

    # Build bd list command arguments
    bd_args = ["bd", "list", "--json"]

    if filter_status == "open":
        bd_args.extend(["--status", "open"])
    elif filter_status == "in_progress":
        bd_args.extend(["--status", "in_progress"])
    elif filter_status == "all":
        bd_args.append("--all")

    try:
        result = subprocess.run(
            bd_args,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            # Fallback to plain text output
            return _fetch_beads_tasks_plaintext(filter_status)

        # Parse JSON output
        try:
            tasks_data = json.loads(result.stdout)
            tasks = []
            for item in tasks_data:
                # Filter out closed items and entries without id/title
                if (item.get("status") != "closed" and
                    item.get("id") and
                    item.get("title")):
                    tasks.append({
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "status": item.get("status", "open")
                    })
            return tasks
        except json.JSONDecodeError:
            return _fetch_beads_tasks_plaintext(filter_status)

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _fetch_beads_tasks_plaintext(filter_status: str = "open") -> List[Dict]:
    """
    Fallback plain text parsing for bd list output.

    Format: "○ cnzb-xxx [● P2] [task] - Title here"
    """
    bd_args = ["bd", "list"]

    if filter_status == "open":
        bd_args.extend(["--status", "open"])
    elif filter_status == "in_progress":
        bd_args.extend(["--status", "in_progress"])
    elif filter_status == "all":
        bd_args.append("--all")

    try:
        result = subprocess.run(
            bd_args,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return []

        tasks = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue

            # Extract ID (e.g., cnzb-xxx)
            id_match = re.search(r'([a-z]+-[a-z0-9]+)', line, re.IGNORECASE)
            if not id_match:
                continue
            task_id = id_match.group(1)

            # Extract title (after last " - ")
            if " - " in line:
                title = line.split(" - ")[-1].strip()
            else:
                title = line.strip()

            if task_id and title:
                tasks.append({
                    "id": task_id,
                    "title": title,
                    "status": "open"
                })

        return tasks
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def get_beads_count(beads_dir: str = ".beads") -> int:
    """
    Get count of open beads issues.

    Args:
        beads_dir: Path to .beads directory (default: ".beads")

    Returns:
        Number of open tasks, 0 if beads unavailable.
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

        if result.returncode == 0:
            try:
                tasks_data = json.loads(result.stdout)
                # Count non-closed tasks
                count = sum(1 for item in tasks_data if item.get("status") != "closed")
                return count
            except json.JSONDecodeError:
                pass

        # Fallback: line count
        result = subprocess.run(
            ["bd", "list"],
            capture_output=True,
            text=True,
            timeout=30
        )
        return len([l for l in result.stdout.strip().split("\n") if l.strip()])

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 0


def check_github_available() -> bool:
    """
    Check if GitHub CLI (gh) is available and authenticated.

    Returns:
        True if gh is available, authenticated, and in a repo with GitHub remote.
    """
    # Check for gh command
    try:
        subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
    except FileNotFoundError:
        return False

    # Check if authenticated
    result = subprocess.run(
        ["gh", "auth status"],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode != 0:
        return False

    # Check if in a git repo with GitHub remote
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return False
        return "github.com" in result.stdout
    except FileNotFoundError:
        return False


def fetch_github_tasks(
    label: Optional[str] = None,
    limit: int = 50
) -> List[Dict]:
    """
    Fetch issues from GitHub.

    Args:
        label: Label to filter by (optional)
        limit: Maximum number of issues (default: 50)

    Returns:
        List of task dictionaries with 'number', 'title', 'labels' fields.
    """
    if not check_github_available():
        return []

    # Build gh command
    gh_args = ["gh", "issue", "list", "--state", "open", "--limit", str(limit), "--json", "number,title,labels"]
    if label:
        gh_args.extend(["--label", label])

    try:
        result = subprocess.run(
            gh_args,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return []

        try:
            issues_data = json.loads(result.stdout)
            tasks = []
            for item in issues_data:
                tasks.append({
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "labels": [l.get("name") for l in item.get("labels", [])]
                })
            return tasks
        except json.JSONDecodeError:
            return []

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


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

    gh_args = ["gh", "issue", "list", "--state", "open", "--json", "number"]
    if label:
        gh_args.extend(["--label", label])

    try:
        result = subprocess.run(
            gh_args,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            try:
                issues_data = json.loads(result.stdout)
                return len(issues_data)
            except json.JSONDecodeError:
                pass

        # Fallback: line count
        result = subprocess.run(
            ["gh", "issue", "list", "--state", "open"],
            capture_output=True,
            text=True,
            timeout=30
        )
        return len([l for l in result.stdout.strip().split("\n") if l.strip()])

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 0


def get_github_labels() -> List[str]:
    """
    Get available labels from GitHub repo.

    Returns:
        List of label names, empty list if unavailable.
    """
    if not check_github_available():
        return []

    try:
        result = subprocess.run(
            ["gh", "label", "list", "--json", "name", "--jq", ".[].name"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            try:
                labels = json.loads(result.stdout)
                return labels
            except json.JSONDecodeError:
                pass

        return []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def extract_prd_tasks(prd_file: str) -> List[Dict]:
    """
    Extract tasks from a PRD/specification document.

    Supports:
    - Checkbox items: - [ ] or - [x]
    - Numbered list items: 1. 2. 3.
    - Task section headings: # TODO, # Tasks, etc.

    Args:
        prd_file: Path to the PRD file

    Returns:
        List of task dictionaries with 'text', 'checked' fields.
    """
    if not os.path.isfile(prd_file):
        return []

    tasks = []

    try:
        with open(prd_file, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.split("\n")

        # Look for checkbox items
        checkbox_pattern = re.compile(r'^[\s]*[-*][\s]*\[[\s]*([xX ]?)[\s]*\](.*)$')
        for line in lines:
            match = checkbox_pattern.match(line)
            if match:
                checked = match.group(1).strip().lower() in ('x', 'X')
                task_text = match.group(2).strip()
                if task_text:
                    tasks.append({
                        "text": task_text,
                        "checked": checked
                    })

        # Look for numbered list items (first 20 only)
        numbered_pattern = re.compile(r'^[\s]*[0-9]+\.[\s]+(.+)$')
        for line in lines:
            match = numbered_pattern.match(line)
            if match:
                task_text = match.group(1).strip()
                if task_text and len(tasks) < 30:
                    tasks.append({
                        "text": task_text,
                        "checked": False
                    })

        # Limit to 30 tasks
        return tasks[:30]

    except (IOError, UnicodeDecodeError):
        return []


def prioritize_tasks(tasks: List[Dict]) -> List[Dict]:
    """
    Sort tasks by priority heuristics.

    High priority: "critical", "urgent", "blocker", "breaking", "security", "p0", "p1",
                   "important", "should", "must", "needed", "required", "p2"
    Low priority: "nice to have", "optional", "future", "later", "p3", "p4", "low priority"

    Args:
        tasks: List of task dictionaries with 'text' field

    Returns:
        Tasks sorted into priority groups.
    """
    high_priority = []
    medium_priority = []
    low_priority = []

    high_pattern = re.compile(
        '(' + '|'.join(HIGH_PRIORITY + ["important", "should", "must", "needed", "required", "p2"]) + ')',
        re.IGNORECASE
    )
    low_pattern = re.compile(
        '(' + '|'.join(LOW_PRIORITY) + ')',
        re.IGNORECASE
    )

    for task in tasks:
        text = task.get("text", "").lower()

        if high_pattern.search(text):
            high_priority.append(task)
        elif low_pattern.search(text):
            low_priority.append(task)
        else:
            medium_priority.append(task)

    return high_priority + medium_priority + low_priority


def normalize_tasks(tasks: str, source: str = "unknown") -> str:
    """
    Normalize tasks to consistent markdown checkbox format.

    Args:
        tasks: Raw task text (multi-line)
        source: Source identifier (beads, github, prd)

    Returns:
        Normalized tasks in markdown checkbox format.
    """
    if not tasks:
        return ""

    lines = tasks.strip().split("\n")
    normalized = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Already in checkbox format
        if re.match(r'^[\s]*-[\s]*\[[\s]*[xX ]?[\s]*\]', line):
            # Normalize the checkbox
            normalized_line = re.sub(r'\[x\]', '[ ]', line, flags=re.IGNORECASE)
            normalized.append(normalized_line)
        # Bullet point without checkbox
        elif re.match(r'^[\s*][-*][\s]+', line):
            text = re.sub(r'^[\s]*[-*][\s]+', '', line)
            normalized.append(f"- [ ] {text}")
        # Numbered item
        elif re.match(r'^[\s]*[0-9]+\.?[\s]+', line):
            text = re.sub(r'^[\s]*[0-9]*\.?[\s]*', '', line)
            normalized.append(f"- [ ] {text}")
        # Plain text
        else:
            normalized.append(f"- [ ] {line}")

    return "\n".join(normalized)


def import_tasks_from_sources(
    sources: List[str],
    prd_file: Optional[str] = None,
    github_label: Optional[str] = None
) -> Tuple[List[Dict], List[str]]:
    """
    Import tasks from multiple sources.

    Args:
        sources: List of sources: "beads", "github", "prd"
        prd_file: Path to PRD file (required if "prd" in sources)
        github_label: GitHub label filter (optional)

    Returns:
        Tuple of (tasks list, source names that had tasks).
    """
    all_tasks = []
    active_sources = []

    # Import from beads
    if "beads" in sources:
        beads_tasks = fetch_beads_tasks()
        if beads_tasks:
            for task in beads_tasks:
                all_tasks.append({
                    "text": f"- [ ] [{task['id']}] {task['title']}",
                    "source": "beads"
                })
            active_sources.append("beads")

    # Import from GitHub
    if "github" in sources:
        github_tasks = fetch_github_tasks(label=github_label)
        if github_tasks:
            for task in github_tasks:
                all_tasks.append({
                    "text": f"- [ ] [#{task['number']}] {task['title']}",
                    "source": "github"
                })
            active_sources.append("github")

    # Import from PRD
    if "prd" in sources and prd_file:
        prd_tasks = extract_prd_tasks(prd_file)
        if prd_tasks:
            for task in prd_tasks:
                checkbox = "[x]" if task.get("checked") else "[ ]"
                all_tasks.append({
                    "text": f"- [ ] {task['text']}",
                    "source": "prd"
                })
            active_sources.append("prd")

    return all_tasks, active_sources

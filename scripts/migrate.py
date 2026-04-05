#!/usr/bin/env python3
"""
Migration script for Ralph projects from flat structure to .ralph/ subfolder.

Version: 2.0.0

This script migrates existing Ralph projects from the old flat structure:
    PROMPT.md, @fix_plan.md (or fix_plan.md), @AGENT.md (or AGENT.md), specs/, logs/
To the new .ralph/ subfolder structure.
"""

import os
import sys
import click
from pathlib import Path
from typing import List, Tuple, Optional
import shutil
from datetime import datetime


# Colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'


def color(text: str, color_code: str) -> str:
    """Apply color to text."""
    return f"{color_code}{text}{NC}"


def log(level: str, message: str) -> None:
    """Log a message with level."""
    colors = {
        "INFO": BLUE,
        "WARN": YELLOW,
        "ERROR": RED,
        "SUCCESS": GREEN
    }
    col = colors.get(level, "")
    print(f"{col}[{level}]{NC} {message}")


# =============================================================================
# DETECTION
# =============================================================================

def is_already_migrated(project_dir: Path) -> bool:
    """
    Check if project is already migrated.

    Returns:
        True if .ralph/ directory exists with key files
    """
    ralph_dir = project_dir / ".ralph"

    if not ralph_dir.exists():
        return False

    prompt = ralph_dir / "PROMPT.md"
    fix_plan = ralph_dir / "fix_plan.md"

    return prompt.exists() or fix_plan.exists()


def needs_migration(project_dir: Path) -> bool:
    """
    Check if project needs migration (has old-style structure).

    Returns:
        True if old files exist that need migration
    """
    # Check for old-style structure (files in root)
    old_files = [
        "PROMPT.md",
        "@fix_plan.md",
        "fix_plan.md",
        "@AGENT.md",
        "AGENT.md"
    ]

    for f in old_files:
        if (project_dir / f).exists():
            return True

    # Check for legacy @-prefixed files in .ralph/
    ralph_dir = project_dir / ".ralph"
    if ralph_dir.exists():
        for f in ["@fix_plan.md", "@AGENT.md"]:
            if (ralph_dir / f).exists():
                return True

    # Check for old directories
    if (project_dir / "specs").exists() and not (ralph_dir / "specs").exists():
        return True
    if (project_dir / "logs").exists() and not (ralph_dir / "logs").exists():
        return True

    return False


# =============================================================================
# BACKUP
# =============================================================================

def create_backup(project_dir: Path) -> Path:
    """
    Create a backup of files before migration.

    Returns:
        Path to backup directory
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = project_dir / f".ralph_backup_{timestamp}"

    log("INFO", f"Creating backup at {backup_dir}")

    backup_dir.mkdir(parents=True, exist_ok=True)

    # Backup files that will be moved
    files_to_backup = [
        "PROMPT.md",
        "@fix_plan.md",
        "fix_plan.md",
        "@AGENT.md",
        "AGENT.md",
        ".call_count",
        ".last_reset",
        ".exit_signals",
        ".response_analysis",
        ".circuit_breaker_state",
        ".circuit_breaker_history",
        ".claude_session_id",
        ".ralph_session",
        "status.json"
    ]

    for f in files_to_backup:
        src = project_dir / f
        if src.exists():
            shutil.copy2(src, backup_dir / f)

    # Backup directories
    for d in ["specs", "logs", "examples", "docs"]:
        src = project_dir / d
        if src.exists() and src.is_dir():
            dest = backup_dir / d if d != "docs" else backup_dir / "docs_generated"
            shutil.copytree(src, dest, dirs_exist_ok=True)

    # Backup legacy @-prefixed files in .ralph/
    ralph_dir = project_dir / ".ralph"
    if ralph_dir.exists():
        for f in ["@fix_plan.md", "@AGENT.md"]:
            src = ralph_dir / f
            if src.exists():
                shutil.copy2(src, backup_dir / f)

    return backup_dir


# =============================================================================
# MIGRATION
# =============================================================================

def migrate_project(project_dir: Path, backup_dir: Path) -> None:
    """
    Migrate project to new structure.

    Migration mapping:
        PROMPT.md -> .ralph/PROMPT.md
        @fix_plan.md -> .ralph/fix_plan.md (renamed)
        fix_plan.md -> .ralph/fix_plan.md
        @AGENT.md -> .ralph/AGENT.md (renamed)
        AGENT.md -> .ralph/AGENT.md
        specs/ -> .ralph/specs/
        logs/ -> .ralph/logs/
        docs/generated/ -> .ralph/docs/generated/
        .call_count -> .ralph/.call_count
        (etc.)
    """
    log("INFO", "Starting migration...")

    # Create .ralph directory structure
    ralph_dirs = [
        project_dir / ".ralph",
        project_dir / ".ralph" / "specs",
        project_dir / ".ralph" / "examples",
        project_dir / ".ralph" / "logs",
        project_dir / ".ralph" / "docs" / "generated"
    ]
    for d in ralph_dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Move main configuration files
    # Priority: root file wins over .ralph/ file

    # PROMPT.md
    src = project_dir / "PROMPT.md"
    if src.exists():
        log("INFO", "Moving PROMPT.md to .ralph/")
        shutil.move(str(src), str(project_dir / ".ralph" / "PROMPT.md"))

    # @fix_plan.md or fix_plan.md
    src_at = project_dir / "@fix_plan.md"
    src_no_at = project_dir / "fix_plan.md"
    src_ralph_at = project_dir / ".ralph" / "@fix_plan.md"

    if src_at.exists():
        if src_ralph_at.exists():
            log("WARN", "Removing .ralph/@fix_plan.md (superseded by root @fix_plan.md)")
            src_ralph_at.unlink()
        log("INFO", "Moving @fix_plan.md to .ralph/fix_plan.md (removing @ prefix)")
        shutil.move(str(src_at), str(project_dir / ".ralph" / "fix_plan.md"))
    elif src_no_at.exists():
        if src_ralph_at.exists():
            log("WARN", "Removing .ralph/@fix_plan.md (superseded by root fix_plan.md)")
            src_ralph_at.unlink()
        log("INFO", "Moving fix_plan.md to .ralph/")
        shutil.move(str(src_no_at), str(project_dir / ".ralph" / "fix_plan.md"))
    elif src_ralph_at.exists():
        log("INFO", "Renaming .ralph/@fix_plan.md to .ralph/fix_plan.md")
        shutil.move(str(src_ralph_at), str(project_dir / ".ralph" / "fix_plan.md"))

    # @AGENT.md or AGENT.md
    src_at = project_dir / "@AGENT.md"
    src_no_at = project_dir / "AGENT.md"
    src_ralph_at = project_dir / ".ralph" / "@AGENT.md"

    if src_at.exists():
        if src_ralph_at.exists():
            log("WARN", "Removing .ralph/@AGENT.md (superseded by root @AGENT.md)")
            src_ralph_at.unlink()
        log("INFO", "Moving @AGENT.md to .ralph/AGENT.md (removing @ prefix)")
        shutil.move(str(src_at), str(project_dir / ".ralph" / "AGENT.md"))
    elif src_no_at.exists():
        if src_ralph_at.exists():
            log("WARN", "Removing .ralph/@AGENT.md (superseded by root AGENT.md)")
            src_ralph_at.unlink()
        log("INFO", "Moving AGENT.md to .ralph/")
        shutil.move(str(src_no_at), str(project_dir / ".ralph" / "AGENT.md"))
    elif src_ralph_at.exists():
        log("INFO", "Renaming .ralph/@AGENT.md to .ralph/AGENT.md")
        shutil.move(str(src_ralph_at), str(project_dir / ".ralph" / "AGENT.md"))

    # Move specs directory
    src = project_dir / "specs"
    if src.exists():
        log("INFO", "Moving specs/ to .ralph/specs/")
        if any(src.iterdir()):  # if not empty
            for item in src.iterdir():
                dest = project_dir / ".ralph" / "specs" / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)
        shutil.rmtree(src)

    # Move logs directory
    src = project_dir / "logs"
    if src.exists():
        log("INFO", "Moving logs/ to .ralph/logs/")
        if any(src.iterdir()):
            for item in src.iterdir():
                dest = project_dir / ".ralph" / "logs" / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)
        shutil.rmtree(src)

    # Move docs/generated
    src = project_dir / "docs" / "generated"
    if src.exists():
        log("INFO", "Moving docs/generated/ to .ralph/docs/generated/")
        if any(src.iterdir()):
            for item in src.iterdir():
                dest = project_dir / ".ralph" / "docs" / "generated" / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)
        shutil.rmtree(src.parent)
        if src.parent.parent.exists() and not any(src.parent.parent.iterdir()):
            src.parent.parent.rmdir()

    # Move hidden state files
    state_files = [
        ".call_count",
        ".last_reset",
        ".exit_signals",
        ".response_analysis",
        ".circuit_breaker_state",
        ".circuit_breaker_history",
        ".claude_session_id",
        ".ralph_session",
        ".ralph_session_history",
        ".json_parse_result",
        ".last_output_length",
        "status.json"
    ]

    for f in state_files:
        src = project_dir / f
        if src.exists():
            log("INFO", f"Moving {f} to .ralph/")
            shutil.move(str(src), str(project_dir / ".ralph" / f))

    # Move examples directory
    src = project_dir / "examples"
    if src.exists():
        dest = project_dir / ".ralph" / "examples"
        if not dest.exists() or not any(dest.iterdir()):
            log("INFO", "Moving examples/ to .ralph/examples/")
            dest.mkdir(parents=True, exist_ok=True)
            if any(src.iterdir()):
                for item in src.iterdir():
                    if item.is_dir():
                        shutil.copytree(item, dest / item.name, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dest / item.name)
            shutil.rmtree(src)

    log("SUCCESS", "Migration completed successfully!")


# =============================================================================
# CLI COMMAND
# =============================================================================

@click.command()
@click.argument("project_dir", default=".")
@click.option("--backup/--no-backup", default=True, help="Create backup before migration")
@click.option("--force", is_flag=True, help="Force migration even if already migrated")
def migrate(project_dir: str, backup: bool, force: bool) -> None:
    """
    Migrate Ralph project from flat structure to .ralph/ subfolder.

    Old structure (flat):
        project/
        ├── PROMPT.md
        ├── fix_plan.md (or @fix_plan.md)
        ├── AGENT.md (or @AGENT.md)
        ├── specs/
        ├── logs/
        └── src/

    New structure (.ralph/ subfolder):
        project/
        ├── .ralph/
        │   ├── PROMPT.md
        │   ├── fix_plan.md
        │   ├── AGENT.md
        │   ├── specs/
        │   ├── logs/
        │   └── docs/generated/
        └── src/

    Examples:

        migrate              # Migrate current directory

        migrate ./my-project # Migrate specific project

        migrate --no-backup  # Migrate without backup
    """
    project_path = Path(project_dir).resolve()

    log("INFO", f"Checking project directory: {project_path}")

    # Check if already migrated
    if is_already_migrated(project_path):
        log("SUCCESS", "Project is already using the new .ralph/ structure")
        if force:
            log("INFO", "Forcing migration...")
        else:
            log("INFO", "Use --force to overwrite existing configuration.")
            sys.exit(0)

    # Check if needs migration
    if not needs_migration(project_path):
        log("WARN", "No Ralph project files found. Nothing to migrate.")
        log("INFO", "Expected files: PROMPT.md, fix_plan.md (or @fix_plan.md), AGENT.md (or @AGENT.md), specs/, logs/")
        sys.exit(0)

    # Create backup
    backup_dir = None
    if backup:
        backup_dir = create_backup(project_path)
        log("SUCCESS", f"Backup created at: {backup_dir}")

    # Perform migration
    migrate_project(project_path, backup_dir)

    print()
    log("INFO", "Migration summary:")
    print("  - Project files moved to .ralph/ subfolder")
    print(f"  - Backup saved at: {backup_dir}")
    print("  - src/ directory preserved at project root")
    print()
    log("INFO", "Next steps:")
    print("  1. Verify the migration by checking .ralph/ contents")
    print("  2. Run 'ralph --status' to verify Ralph can read the new structure")
    print("  3. If everything works, you can delete the backup directory")


if __name__ == "__main__":
    migrate()

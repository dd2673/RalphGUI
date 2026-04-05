#!/usr/bin/env python3
"""
Ralph Migrate - Migrate Ralph projects from flat structure to .ralph/ subfolder.
"""

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


def log(level: str, message: str):
    """Print colored log message."""
    colors = {
        "INFO": "\033[94m",     # Blue
        "WARN": "\033[93m",     # Yellow
        "ERROR": "\033[91m",    # Red
        "SUCCESS": "\033[92m",  # Green
    }
    reset = "\033[0m"
    color = colors.get(level, "")
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{timestamp}] [{level}] {message}{reset}")


def is_already_migrated(project_dir: Path) -> bool:
    """Check if project is already migrated to .ralph/ structure."""
    ralph_dir = project_dir / ".ralph"
    if not ralph_dir.exists():
        return False

    # Check for key files
    has_prompt = (ralph_dir / "PROMPT.md").exists()
    has_fix_plan = (ralph_dir / "fix_plan.md").exists() or (ralph_dir / "@fix_plan.md").exists()

    return has_prompt and has_fix_plan


def needs_migration(project_dir: Path) -> bool:
    """Check if project needs migration (has old-style structure)."""
    # Check for old-style files in root
    old_files = [
        project_dir / "PROMPT.md",
        project_dir / "@fix_plan.md",
        project_dir / "fix_plan.md",
        project_dir / "@AGENT.md",
        project_dir / "AGENT.md",
    ]

    for f in old_files:
        if f.exists():
            return True

    # Check for old directories
    if (project_dir / "specs").exists() and not (project_dir / ".ralph" / "specs").exists():
        return True
    if (project_dir / "logs").exists() and not (project_dir / ".ralph" / "logs").exists():
        return True

    # Check for legacy @-prefixed files in .ralph/
    ralph_dir = project_dir / ".ralph"
    if ralph_dir.exists():
        if (ralph_dir / "@fix_plan.md").exists():
            return True
        if (ralph_dir / "@AGENT.md").exists():
            return True

    return False


def create_backup(project_dir: Path) -> Path:
    """Create backup of files before migration."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = project_dir / f".ralph_backup_{timestamp}"

    log("INFO", f"Creating backup at {backup_dir}")
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Backup files that will be moved
    files_to_backup = [
        ("PROMPT.md", None),
        ("@fix_plan.md", None),
        ("fix_plan.md", None),
        ("@AGENT.md", None),
        ("AGENT.md", None),
        (".call_count", None),
        (".last_reset", None),
        (".exit_signals", None),
        (".response_analysis", None),
        (".circuit_breaker_state", None),
        (".circuit_breaker_history", None),
        (".claude_session_id", None),
        (".ralph_session", None),
        (".ralph_session_history", None),
        (".json_parse_result", None),
        (".last_output_length", None),
        ("status.json", None),
    ]

    for fname, _ in files_to_backup:
        src = project_dir / fname
        if src.exists():
            shutil.copy2(src, backup_dir / fname)

    # Backup directories
    dirs_to_backup = [
        ("specs", None),
        ("logs", None),
        ("examples", None),
    ]

    for dirname, _ in dirs_to_backup:
        src = project_dir / dirname
        if src.exists():
            shutil.copytree(src, backup_dir / dirname, dirs_exist_ok=True)

    # Backup docs/generated with renamed target
    docs_gen = project_dir / "docs" / "generated"
    if docs_gen.exists():
        backup_docs = backup_dir / "docs"
        backup_docs.mkdir(exist_ok=True)
        shutil.copytree(docs_gen, backup_docs / "generated", dirs_exist_ok=True)

    # Backup legacy @-prefixed files in .ralph/
    ralph_dir = project_dir / ".ralph"
    if ralph_dir.exists():
        for fname in ["@fix_plan.md", "@AGENT.md"]:
            src = ralph_dir / fname
            if src.exists():
                shutil.copy2(src, backup_dir / fname)

    log("SUCCESS", f"Backup created at: {backup_dir}")
    return backup_dir


def migrate_project(project_dir: Path, backup_dir: Path) -> None:
    """Migrate project to new .ralph/ structure."""
    log("INFO", "Starting migration...")

    # Create .ralph directory structure
    ralph_dir = project_dir / ".ralph"
    (ralph_dir / "specs" / "stdlib").mkdir(parents=True, exist_ok=True)
    (ralph_dir / "logs").mkdir(exist_ok=True)
    (ralph_dir / "docs" / "generated").mkdir(parents=True, exist_ok=True)

    # Move PROMPT.md
    prompt_src = project_dir / "PROMPT.md"
    if prompt_src.exists():
        log("INFO", "Moving PROMPT.md to .ralph/")
        shutil.move(str(prompt_src), str(ralph_dir / "PROMPT.md"))

    # Handle fix_plan.md - priority: root file wins over .ralph/ file
    fix_src = None
    if (project_dir / "@fix_plan.md").exists():
        fix_src = project_dir / "@fix_plan.md"
        log("INFO", "Moving @fix_plan.md to .ralph/fix_plan.md (renaming to remove @ prefix)")
        # Remove any existing .ralph/@fix_plan.md
        if (ralph_dir / "@fix_plan.md").exists():
            log("WARN", "Removing .ralph/@fix_plan.md (superseded by root @fix_plan.md)")
            (ralph_dir / "@fix_plan.md").unlink()
        shutil.move(str(fix_src), str(ralph_dir / "fix_plan.md"))
    elif (project_dir / "fix_plan.md").exists():
        fix_src = project_dir / "fix_plan.md"
        log("INFO", "Moving fix_plan.md to .ralph/")
        if (ralph_dir / "@fix_plan.md").exists():
            log("WARN", "Removing .ralph/@fix_plan.md (superseded by root fix_plan.md)")
            (ralph_dir / "@fix_plan.md").unlink()
        shutil.move(str(fix_src), str(ralph_dir / "fix_plan.md"))
    elif (ralph_dir / "@fix_plan.md").exists():
        log("INFO", "Renaming .ralph/@fix_plan.md to .ralph/fix_plan.md")
        shutil.move(str(ralph_dir / "@fix_plan.md"), str(ralph_dir / "fix_plan.md"))

    # Handle AGENT.md - priority: root file wins over .ralph/ file
    agent_src = None
    if (project_dir / "@AGENT.md").exists():
        agent_src = project_dir / "@AGENT.md"
        log("INFO", "Moving @AGENT.md to .ralph/AGENT.md (renaming to remove @ prefix)")
        if (ralph_dir / "@AGENT.md").exists():
            log("WARN", "Removing .ralph/@AGENT.md (superseded by root @AGENT.md)")
            (ralph_dir / "@AGENT.md").unlink()
        shutil.move(str(agent_src), str(ralph_dir / "AGENT.md"))
    elif (project_dir / "AGENT.md").exists():
        agent_src = project_dir / "AGENT.md"
        log("INFO", "Moving AGENT.md to .ralph/")
        if (ralph_dir / "@AGENT.md").exists():
            log("WARN", "Removing .ralph/@AGENT.md (superseded by root AGENT.md)")
            (ralph_dir / "@AGENT.md").unlink()
        shutil.move(str(agent_src), str(ralph_dir / "AGENT.md"))
    elif (ralph_dir / "@AGENT.md").exists():
        log("INFO", "Renaming .ralph/@AGENT.md to .ralph/AGENT.md")
        shutil.move(str(ralph_dir / "@AGENT.md"), str(ralph_dir / "AGENT.md"))

    # Move specs directory contents
    specs_src = project_dir / "specs"
    if specs_src.exists():
        log("INFO", "Moving specs/ to .ralph/specs/")
        if any(specs_src.iterdir()):
            # Copy contents preserving attributes
            for item in specs_src.rglob("*"):
                if item.is_file():
                    rel_path = item.relative_to(specs_src)
                    dest_file = ralph_dir / "specs" / rel_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest_file)
            # Verify copy before delete
            if (ralph_dir / "specs").exists() and any((ralph_dir / "specs").iterdir()):
                shutil.rmtree(specs_src)
            else:
                log("WARN", "Failed to copy specs/, keeping original (backup available)")
        else:
            specs_src.rmdir()

    # Move logs directory contents
    logs_src = project_dir / "logs"
    if logs_src.exists():
        log("INFO", "Moving logs/ to .ralph/logs/")
        if any(logs_src.iterdir()):
            for item in logs_src.rglob("*"):
                if item.is_file():
                    rel_path = item.relative_to(logs_src)
                    dest_file = ralph_dir / "logs" / rel_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest_file)
            if (ralph_dir / "logs").exists() and any((ralph_dir / "logs").iterdir()):
                shutil.rmtree(logs_src)
            else:
                log("WARN", "Failed to copy logs/, keeping original (backup available)")
        else:
            logs_src.rmdir()

    # Move docs/generated contents
    docs_gen_src = project_dir / "docs" / "generated"
    if docs_gen_src.exists():
        log("INFO", "Moving docs/generated/ to .ralph/docs/generated/")
        if any(docs_gen_src.iterdir()):
            for item in docs_gen_src.rglob("*"):
                if item.is_file():
                    rel_path = item.relative_to(docs_gen_src)
                    dest_file = ralph_dir / "docs" / "generated" / rel_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest_file)
            if (ralph_dir / "docs" / "generated").exists() and any((ralph_dir / "docs" / "generated").iterdir()):
                shutil.rmtree(docs_gen_src)
                # Remove docs directory if empty
                docs_dir = project_dir / "docs"
                if docs_dir.exists() and not any(docs_dir.iterdir()):
                    docs_dir.rmdir()
            else:
                log("WARN", "Failed to copy docs/generated/, keeping original (backup available)")
        else:
            shutil.rmtree(docs_gen_src)
            docs_dir = project_dir / "docs"
            if docs_dir.exists() and not any(docs_dir.iterdir()):
                docs_dir.rmdir()

    # Move hidden state files
    state_files = [
        ".call_count", ".last_reset", ".exit_signals", ".response_analysis",
        ".circuit_breaker_state", ".circuit_breaker_history", ".claude_session_id",
        ".ralph_session", ".ralph_session_history", ".json_parse_result",
        ".last_output_length", "status.json"
    ]

    for fname in state_files:
        src = project_dir / fname
        if src.exists():
            log("INFO", f"Moving {fname} to .ralph/")
            shutil.move(str(src), str(ralph_dir / fname))

    # Move examples directory
    examples_src = project_dir / "examples"
    if examples_src.exists():
        examples_dst = ralph_dir / "examples"
        # Only move if target doesn't exist or is empty
        if not examples_dst.exists() or not any(examples_dst.iterdir()):
            log("INFO", "Moving examples/ to .ralph/examples/")
            examples_dst.mkdir(exist_ok=True)
            if any(examples_src.iterdir()):
                for item in examples_src.rglob("*"):
                    if item.is_file():
                        rel_path = item.relative_to(examples_src)
                        dest_file = examples_dst / rel_path
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dest_file)
                if examples_dst.exists() and any(examples_dst.iterdir()):
                    shutil.rmtree(examples_src)
                else:
                    log("WARN", "Failed to copy examples/, keeping original (backup available)")
            else:
                shutil.rmtree(examples_src)

    log("SUCCESS", "Migration completed successfully!")


def main():
    parser = argparse.ArgumentParser(
        description="Ralph Migrate - Migrate to .ralph/ subfolder structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ralph_migrate.py                           # Migrate current directory
  ralph_migrate.py ./my-project              # Migrate specific project
  ralph_migrate.py ./my-project --no-backup  # Skip backup
  ralph_migrate.py ./my-project --force      # Force migration even if already migrated
        """
    )
    parser.add_argument(
        "project_dir",
        nargs="?",
        default=".",
        help="Path to the Ralph project to migrate (default: current directory)"
    )
    backup_group = parser.add_mutually_exclusive_group(required=False)
    backup_group.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help="Create backup before migration (default: True)"
    )
    backup_group.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup creation"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force migration even if already migrated"
    )

    args = parser.parse_args()

    # Convert to absolute path
    project_dir = Path(args.project_dir).resolve()

    log("INFO", f"Checking project directory: {project_dir}")

    # Check if already migrated
    if is_already_migrated(project_dir):
        if args.force:
            log("WARN", "Project already migrated but forcing migration...")
        else:
            log("SUCCESS", "Project is already using the new .ralph/ structure")
            sys.exit(0)

    # Check if needs migration
    if not needs_migration(project_dir):
        log("WARN", "No Ralph project files found. Nothing to migrate.")
        log("INFO", "Expected files: PROMPT.md, fix_plan.md (or @fix_plan.md), AGENT.md (or @AGENT.md), specs/, logs/")
        sys.exit(0)

    # Create backup unless --no-backup
    backup_dir = None
    if not args.no_backup:
        backup_dir = create_backup(project_dir)

    # Perform migration
    migrate_project(project_dir, backup_dir)

    print()
    log("INFO", "Migration summary:")
    print("  - Project files moved to .ralph/ subfolder")
    if backup_dir:
        print(f"  - Backup saved at: {backup_dir}")
    print("  - src/ directory preserved at project root")
    print()
    log("INFO", "Next steps:")
    print("  1. Verify the migration by checking .ralph/ contents")
    print("  2. Run 'ralph --status' to verify Ralph can read the new structure")
    print("  3. If everything works, you can delete the backup directory")


if __name__ == "__main__":
    main()

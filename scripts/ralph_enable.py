#!/usr/bin/env python3
"""
Ralph Enable - Interactive Wizard for Existing Projects

Adds Ralph configuration to an existing codebase.
"""

import os
import sys
import click
from pathlib import Path
from typing import Optional, List, Dict, Any
import subprocess
import json
import shutil
from datetime import datetime


# Exit codes
ENABLE_SUCCESS = 0
ENABLE_ERROR = 1
ENABLE_ALREADY_ENABLED = 2
ENABLE_INVALID_ARGS = 3
ENABLE_FILE_NOT_FOUND = 4
ENABLE_DEPENDENCY_MISSING = 5

# Colors
CYAN = '\033[0;36m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
BOLD = '\033[1m'
NC = '\033[0m'


def color(text: str, color_code: str) -> str:
    """Apply color to text."""
    return f"{color_code}{text}{NC}"


def print_header(title: str, phase: str = "") -> None:
    """Print a section header."""
    print()
    print(color("━" * 60, BOLD))
    if phase:
        print(color(f"  {title}", BOLD) + color(f"({phase})", CYAN))
    else:
        print(color(f"  {title}", BOLD))
    print(color("━" * 60, BOLD))
    print()


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"{GREEN}✓{NC} {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"{YELLOW}⚠{NC} {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"{RED}✗{NC} {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"{CYAN}ℹ{NC} {message}")


def print_detection_result(label: str, value: str, available: bool = True) -> None:
    """Print a detection result with status."""
    if available:
        print(f"  {GREEN}✓{NC} {label}: {BOLD}{value}{NC}")
    else:
        print(f"  {YELLOW}○{NC} {label}: {value}")


def confirm(prompt: str, default: str = "n") -> bool:
    """Ask a yes/no question."""
    yn_hint = "[y/N]"
    if default.lower() == "y":
        yn_hint = "[Y/n]"

    while True:
        response = input(f"{CYAN}{prompt}{NC} {yn_hint}: ").strip().lower()
        if not response:
            response = default.lower()
        if response in ("y", "yes"):
            return True
        elif response in ("n", "no"):
            return False
        else:
            print_warning("Please answer yes (y) or no (n)")


def prompt_text(prompt: str, default: str = "") -> str:
    """Ask for text input with optional default."""
    if default:
        response = input(f"{CYAN}{prompt}{NC} [{default}]: ").strip()
    else:
        response = input(f"{CYAN}{prompt}{NC}: ").strip()

    return response if response else default


def prompt_number(prompt: str, default: int = 0, min_val: int = 0, max_val: int = 9999) -> int:
    """Ask for numeric input with optional default and range."""
    while True:
        if default:
            response = input(f"{CYAN}{prompt}{NC} [{default}]: ").strip()
        else:
            response = input(f"{CYAN}{prompt}{NC}: ").strip()

        if not response:
            return default

        try:
            num = int(response)
            if num < min_val:
                print_warning(f"Value must be at least {min_val}")
                continue
            if num > max_val:
                print_warning(f"Value must be at most {max_val}")
                continue
            return num
        except ValueError:
            print_warning("Please enter a valid number")


def select_option(prompt: str, options: List[str]) -> str:
    """Present a list of options for single selection."""
    print(f"\n{BOLD}{prompt}{NC}")
    print()

    for i, opt in enumerate(options, 1):
        print(f"  {CYAN}{i}){NC} {opt}")

    print()

    while True:
        response = input(f"Select option [1-{len(options)}]: ").strip()
        try:
            idx = int(response) - 1
            if 0 <= idx < len(options):
                return options[idx]
            print_warning(f"Please enter a number between 1 and {len(options)}")
        except ValueError:
            print_warning(f"Please enter a number between 1 and {len(options)}")


def select_multiple(prompt: str, options: List[str]) -> List[int]:
    """Present checkboxes for multi-selection. Returns list of selected indices."""
    selected = [False] * len(options)

    print(f"\n{BOLD}{prompt}{NC}")
    print(color("(Enter numbers to toggle, press Enter when done)", CYAN))
    print()

    while True:
        for i, opt in enumerate(options):
            checkbox = "[ ]"
            if selected[i]:
                checkbox = f"[{GREEN}x{NC}]"
            print(f"  {CYAN}{i + 1}){NC} {checkbox} {opt}")

        print()
        response = input("Toggle [1-{}] or Enter to confirm: ".format(len(options))).strip()

        if not response:
            break

        try:
            idx = int(response) - 1
            if 0 <= idx < len(options):
                selected[idx] = not selected[idx]
            else:
                print_warning(f"Please enter a number between 1 and {len(options)}")
        except ValueError:
            print_warning(f"Please enter a number between 1 and {len(options)}")

        # Clear previous display
        for _ in range(len(options) + 2):
            print("\033[A\033[K]")

    return [i for i, s in enumerate(selected) if s]


# =============================================================================
# PROJECT DETECTION
# =============================================================================

def detect_project_context(project_dir: Path) -> Dict[str, str]:
    """Detect project type, name, and build commands."""
    result = {
        "name": "",
        "type": "unknown",
        "framework": "",
        "build_cmd": "",
        "test_cmd": "",
        "run_cmd": ""
    }

    # Detect from package.json (JavaScript/TypeScript)
    pkg_json = project_dir / "package.json"
    if pkg_json.exists():
        try:
            with open(pkg_json) as f:
                pkg = json.load(f)
            result["name"] = pkg.get("name", "")
            result["type"] = "javascript"

            # Check for TypeScript
            if "typescript" in pkg.get("dependencies", {}) or "typescript" in pkg.get("devDependencies", {}):
                result["type"] = "typescript"

            # Detect framework
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "next" in deps:
                result["framework"] = "nextjs"
            elif "express" in deps:
                result["framework"] = "express"
            elif "react" in deps:
                result["framework"] = "react"
            elif "vue" in deps:
                result["framework"] = "vue"

            # Set build commands
            result["build_cmd"] = "npm run build"
            result["test_cmd"] = "npm test"
            result["run_cmd"] = "npm start"

            # Check for yarn
            if (project_dir / "yarn.lock").exists():
                result["build_cmd"] = "yarn build"
                result["test_cmd"] = "yarn test"
                result["run_cmd"] = "yarn start"

            # Check for pnpm
            if (project_dir / "pnpm-lock.yaml").exists():
                result["build_cmd"] = "pnpm build"
                result["test_cmd"] = "pnpm test"
                result["run_cmd"] = "pnpm start"
        except (json.JSONDecodeError, IOError):
            pass

    # Detect from pyproject.toml or setup.py (Python)
    if not result["name"]:
        pyproject = project_dir / "pyproject.toml"
        if pyproject.exists():
            result["type"] = "python"
            try:
                with open(pyproject) as f:
                    content = f.read()
                    # Extract name
                    for line in content.split("\n"):
                        if line.startswith("name"):
                            result["name"] = line.split("=")[1].strip().strip('"').strip("'")
                            break
                    # Detect framework
                    if "fastapi" in content:
                        result["framework"] = "fastapi"
                    elif "django" in content:
                        result["framework"] = "django"
                    elif "flask" in content:
                        result["framework"] = "flask"

                result["build_cmd"] = "pip install -e ."
                result["test_cmd"] = "pytest"
                result["run_cmd"] = f"python -m {result['name'] or 'main'}"
            except IOError:
                pass

    # Detect from Cargo.toml (Rust)
    cargo = project_dir / "Cargo.toml"
    if cargo.exists() and not result["name"]:
        result["type"] = "rust"
        try:
            with open(cargo) as f:
                content = f.read()
                for line in content.split("\n"):
                    if line.startswith("name"):
                        result["name"] = line.split("=")[1].strip().strip('"').strip("'")
                        break
            result["build_cmd"] = "cargo build"
            result["test_cmd"] = "cargo test"
            result["run_cmd"] = "cargo run"
        except IOError:
            pass

    # Detect from go.mod (Go)
    gomod = project_dir / "go.mod"
    if gomod.exists() and not result["name"]:
        result["type"] = "go"
        try:
            with open(gomod) as f:
                first_line = f.readline()
                result["name"] = first_line.replace("module ", "").strip()
            result["build_cmd"] = "go build"
            result["test_cmd"] = "go test ./..."
            result["run_cmd"] = "go run ."
        except IOError:
            pass

    # Fallback project name to folder name
    if not result["name"]:
        result["name"] = project_dir.name

    return result


def detect_git_info(project_dir: Path) -> Dict[str, Any]:
    """Detect git repository information."""
    result = {"repo": False, "remote": "", "github": False}

    try:
        # Check if in git repo
        result["repo"] = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=project_dir,
            capture_output=True,
            timeout=5
        ).returncode == 0

        if result["repo"]:
            # Get remote URL
            remote = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            if remote.returncode == 0:
                result["remote"] = remote.stdout.strip()
                result["github"] = "github.com" in result["remote"]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return result


def detect_task_sources(project_dir: Path) -> Dict[str, Any]:
    """Detect available task sources."""
    result = {
        "beads_available": False,
        "github_available": False,
        "prd_files": []
    }

    # Check for beads
    if (project_dir / ".beads").is_dir():
        result["beads_available"] = True

    # Check for GitHub
    git_info = detect_git_info(project_dir)
    result["github_available"] = git_info["github"]

    # Search for PRD/spec files
    search_patterns = ["*prd*.md", "*PRD*.md", "*requirements*.md", "*spec*.md", "*specification*.md"]
    for pattern in search_patterns:
        for f in project_dir.glob(pattern):
            if f.is_file():
                result["prd_files"].append(str(f))
        for f in (project_dir / "docs").glob(pattern):
            if f.is_file():
                result["prd_files"].append(str(f))
        for f in (project_dir / "specs").glob(pattern):
            if f.is_file():
                result["prd_files"].append(str(f))

    return result


def check_existing_ralph(project_dir: Path) -> tuple:
    """
    Check if .ralph directory exists and its state.

    Returns:
        tuple: (state, missing_files)
        state: "none" | "partial" | "complete"
    """
    ralph_dir = project_dir / ".ralph"

    if not ralph_dir.exists():
        return ("none", [])

    required_files = [
        ".ralph/PROMPT.md",
        ".ralph/fix_plan.md",
        ".ralph/AGENT.md"
    ]

    missing = []
    found = 0

    for file in required_files:
        if (project_dir / file).exists():
            found += 1
        else:
            missing.append(file)

    if found == 0:
        return ("none", missing)
    elif missing:
        return ("partial", missing)
    else:
        return ("complete", missing)


# =============================================================================
# TEMPLATE GENERATION
# =============================================================================

def generate_prompt_md(project_name: str, project_type: str, framework: str = "") -> str:
    """Generate PROMPT.md content."""
    framework_line = f"**Framework:** {framework}" if framework else ""

    return f"""# Ralph Development Instructions

## Context
You are Ralph, an autonomous AI development agent working on the **{project_name}** project.

**Project Type:** {project_type}
{framework_line}

## Current Objectives
- Review the codebase and understand the current state
- Follow tasks in fix_plan.md
- Implement one task per loop
- Write tests for new functionality
- Update documentation as needed

## Key Principles
- ONE task per loop - focus on the most important thing
- Search the codebase before assuming something isn't implemented
- Write comprehensive tests with clear documentation
- Update fix_plan.md with your learnings
- Commit working changes with descriptive messages

## Protected Files (DO NOT MODIFY)
The following files and directories are part of Ralph's infrastructure.
NEVER delete, move, rename, or overwrite these under any circumstances:
- .ralph/ (entire directory and all contents)
- .ralphrc (project configuration)

When performing cleanup, refactoring, or restructuring tasks:
- These files are NOT part of your project code
- They are Ralph's internal control files that keep the development loop running
- Deleting them will break Ralph and halt all autonomous development

## Testing Guidelines
- LIMIT testing to ~20% of your total effort per loop
- PRIORITIZE: Implementation > Documentation > Tests
- Only write tests for NEW functionality you implement

## Build & Run
See AGENT.md for build and run instructions.

## Status Reporting (CRITICAL)

At the end of your response, ALWAYS include this status block:

```
---RALPH_STATUS---
STATUS: IN_PROGRESS | COMPLETE | BLOCKED
TASKS_COMPLETED_THIS_LOOP: <number>
FILES_MODIFIED: <number>
TESTS_STATUS: PASSING | FAILING | NOT_RUN
WORK_TYPE: IMPLEMENTATION | TESTING | DOCUMENTATION | REFACTORING
EXIT_SIGNAL: false | true
RECOMMENDATION: <one line summary of what to do next>
---END_RALPH_STATUS---
```

## Current Task
Follow fix_plan.md and choose the most important item to implement next.
"""


def generate_agent_md(build_cmd: str, test_cmd: str, run_cmd: str) -> str:
    """Generate AGENT.md content."""
    return f"""# Ralph Agent Configuration

## Build Instructions

```bash
# Build the project
{build_cmd}
```

## Test Instructions

```bash
# Run tests
{test_cmd}
```

## Run Instructions

```bash
# Start/run the project
{run_cmd}
```

## Notes
- Update this file when build process changes
- Add environment setup instructions as needed
- Include any pre-requisites or dependencies
"""


def generate_fix_plan_md(tasks: str = "") -> str:
    """Generate fix_plan.md content."""
    if tasks:
        high_priority = tasks
    else:
        high_priority = """- [ ] Review codebase and understand architecture
- [ ] Identify and document key components
- [ ] Set up development environment"""

    return f"""# Ralph Fix Plan

## High Priority
{high_priority}

## Medium Priority
- [ ] Implement core features
- [ ] Add test coverage
- [ ] Update documentation

## Low Priority
- [ ] Performance optimization
- [ ] Code cleanup and refactoring

## Completed
- [x] Project enabled for Ralph

## Notes
- Focus on MVP functionality first
- Ensure each feature is properly tested
- Update this file after each major milestone
"""


def generate_ralphrc(project_name: str, project_type: str, task_sources: str = "local") -> str:
    """Generate .ralphrc content."""
    return f'''# .ralphrc - Ralph project configuration
# Generated by: ralph enable

# Project identification
PROJECT_NAME="{project_name}"
PROJECT_TYPE="{project_type}"

# Claude Code CLI command
CLAUDE_CODE_CMD="claude"

# Loop settings
MAX_CALLS_PER_HOUR=100
CLAUDE_TIMEOUT_MINUTES=15
CLAUDE_OUTPUT_FORMAT="json"

# Tool permissions
ALLOWED_TOOLS="Write,Read,Edit,Bash(git add *),Bash(git commit *),Bash(git diff *),Bash(git log *),Bash(git status),Bash(git push *),Bash(git pull *),Bash(npm *),Bash(pytest)"

# Session management
SESSION_CONTINUITY=true

# Task sources
TASK_SOURCES="{task_sources}"
GITHUB_TASK_LABEL="ralph-task"

# Circuit breaker thresholds
CB_NO_PROGRESS_THRESHOLD=3
CB_SAME_ERROR_THRESHOLD=5

# Auto-update Claude CLI at startup
CLAUDE_AUTO_UPDATE=true
'''


# =============================================================================
# TASK IMPORT
# =============================================================================

def fetch_beads_tasks() -> str:
    """Fetch tasks from beads issue tracker."""
    try:
        result = subprocess.run(
            ["bd", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            import json
            tasks = json.loads(result.stdout)
            lines = []
            for task in tasks:
                if task.get("status") != "closed" and task.get("id") and task.get("title"):
                    lines.append(f"- [ ] [{task['id']}] {task['title']}")
            return "\n".join(lines)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return ""


def fetch_github_tasks(label: str = "ralph-task", limit: int = 50) -> str:
    """Fetch tasks from GitHub issues."""
    try:
        cmd = ["gh", "issue", "list", "--state", "open", "--limit", str(limit), "--json", "number,title"]
        if label:
            cmd.extend(["--label", label])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            issues = json.loads(result.stdout)
            lines = []
            for issue in issues:
                lines.append(f"- [ ] [#{issue['number']}] {issue['title']}")
            return "\n".join(lines)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return ""


def extract_prd_tasks(prd_file: Path) -> str:
    """Extract tasks from a PRD/specification document."""
    if not prd_file.exists():
        return ""

    try:
        with open(prd_file) as f:
            content = f.read()

        lines = []
        for line in content.split("\n"):
            # Look for checkbox items
            import re
            if re.match(r'^[\s]*[-*][\s]*\[[\s]*[xX ]?[\s]*\]', line):
                # Normalize to unchecked format
                line = re.sub(r'\[x\]', '[ ]', line, flags=re.IGNORECASE)
                lines.append(line)
            elif re.match(r'^[\s]*[0-9]+\.[\s]+', line):
                # Numbered list item
                task_text = re.sub(r'^[\s]*[0-9]*\.[\s]*', '', line)
                lines.append(f"- [ ] {task_text}")

        return "\n".join(lines[:30])  # Limit to 30 tasks
    except IOError:
        return ""


# =============================================================================
# FILE CREATION
# =============================================================================

def safe_create_file(target: Path, content: str, force: bool = False) -> bool:
    """Create a file only if it doesn't exist (or force overwrite)."""
    if target.exists() and not force:
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w") as f:
        f.write(content)
    return True


def create_ralph_structure(project_dir: Path) -> None:
    """Create the .ralph/ directory structure."""
    dirs = [
        project_dir / ".ralph",
        project_dir / ".ralph" / "specs",
        project_dir / ".ralph" / "examples",
        project_dir / ".ralph" / "logs",
        project_dir / ".ralph" / "docs" / "generated",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def enable_ralph_in_directory(
    project_dir: Path,
    project_name: str,
    project_type: str,
    framework: str,
    build_cmd: str,
    test_cmd: str,
    run_cmd: str,
    task_content: str,
    force: bool = False
) -> bool:
    """Main function to enable Ralph in a directory."""
    # Create directory structure
    create_ralph_structure(project_dir)

    # Generate and create files
    prompt_content = generate_prompt_md(project_name, project_type, framework)
    safe_create_file(project_dir / ".ralph" / "PROMPT.md", prompt_content, force)

    agent_content = generate_agent_md(build_cmd, test_cmd, run_cmd)
    safe_create_file(project_dir / ".ralph" / "AGENT.md", agent_content, force)

    fix_plan_content = generate_fix_plan_md(task_content)
    safe_create_file(project_dir / ".ralph" / "fix_plan.md", fix_plan_content, force)

    # Generate .ralphrc
    task_sources = "local"
    ralphrc_content = generate_ralphrc(project_name, project_type, task_sources)
    safe_create_file(project_dir / ".ralphrc", ralphrc_content, force)

    return True


# =============================================================================
# CLI COMMAND
# =============================================================================

@click.command()
@click.option("--project-dir", default=".", help="Project directory")
@click.option("--from-source", help="Import tasks from: beads, github, prd")
@click.option("--prd", "prd_file", help="PRD file to convert (when --from prd)")
@click.option("--label", help="GitHub label filter (when --from github)")
@click.option("--force", is_flag=True, help="Overwrite existing .ralph/ configuration")
@click.option("--skip-tasks", is_flag=True, help="Skip task import")
@click.option("--non-interactive", is_flag=True, help="Run with defaults (no prompts)")
def enable(
    project_dir: str = ".",
    from_source: Optional[str] = None,
    prd_file: Optional[str] = None,
    label: Optional[str] = None,
    force: bool = False,
    skip_tasks: bool = False,
    non_interactive: bool = False
) -> None:
    """
    Interactive wizard - Enable Ralph in existing projects.

    This command:

    1. Detects your project type (TypeScript, Python, etc.)

    2. Identifies available task sources (beads, GitHub, PRDs)

    3. Imports tasks from selected sources

    4. Creates .ralph/ configuration directory

    5. Generates PROMPT.md, fix_plan.md, AGENT.md

    6. Creates .ralphrc for project-specific settings
    """
    project_path = Path(project_dir).resolve()

    # Welcome banner
    print()
    print(color("╔════════════════════════════════════════════════════════════╗", BOLD))
    print(color("║          Ralph Enable - Existing Project Wizard            ║", BOLD))
    print(color("╚════════════════════════════════════════════════════════════╝", BOLD))
    print()

    # Phase 1: Environment Detection
    print_header("Environment Detection", "Phase 1 of 5")
    print("Analyzing your project...")
    print()

    # Check existing Ralph state
    state, missing = check_existing_ralph(project_path)
    if state == "complete":
        print_detection_result("Ralph status", "Already enabled")
        if not force:
            print()
            print_warning("Ralph is already enabled in this project.")
            print()
            if non_interactive or confirm("Do you want to continue anyway?", "n"):
                print("Use --force to overwrite.")
                sys.exit(ENABLE_ALREADY_ENABLED)
    elif state == "partial":
        print_detection_result("Ralph status", "Partially configured", False)
        print(f"  Missing files: {', '.join(missing)}")
        print()
    else:
        print_detection_result("Ralph status", "Not configured")

    # Detect project context
    context = detect_project_context(project_path)
    print_detection_result("Project name", context["name"])
    print_detection_result("Project type", context["type"])
    if context["framework"]:
        print_detection_result("Framework", context["framework"])

    # Detect git info
    git_info = detect_git_info(project_path)
    if git_info["repo"]:
        print_detection_result("Git repository", "Yes")
        if git_info["github"]:
            print_detection_result("GitHub remote", "Yes")
    else:
        print_detection_result("Git repository", "No", False)

    # Detect task sources
    task_sources = detect_task_sources(project_path)
    print()
    print("Available task sources:")
    if task_sources["beads_available"]:
        print_detection_result("beads", "available", True)
    if task_sources["github_available"]:
        print_detection_result("GitHub Issues", "available", True)
    if task_sources["prd_files"]:
        print_detection_result("PRD files", f"{len(task_sources['prd_files'])} found", True)

    # Phase 2: Task Source Selection
    print_header("Task Source Selection", "Phase 2 of 5")

    selected_sources = []

    if from_source:
        print(f"Using task source from command line: {from_source}")
        selected_sources = [from_source]
    elif skip_tasks:
        print("Skipping task import (--skip-tasks)")
        selected_sources = []
    elif non_interactive:
        # Auto-select available sources
        if task_sources["beads_available"]:
            selected_sources.append("beads")
        if task_sources["github_available"]:
            selected_sources.append("github")
        print(f"Auto-selected sources: {', '.join(selected_sources) if selected_sources else 'none'}")
    else:
        # Interactive selection
        options = []
        option_keys = []

        if task_sources["beads_available"]:
            options.append("Import from beads")
            option_keys.append("beads")

        if task_sources["github_available"]:
            options.append("Import from GitHub Issues")
            option_keys.append("github")

        if task_sources["prd_files"]:
            options.append(f"Convert PRD/spec document ({len(task_sources['prd_files'])} found)")
            option_keys.append("prd")

        options.append("Start with empty task list")
        option_keys.append("none")

        if len(options) > 1:
            print("Where would you like to import tasks from?")
            print()
            selected_indices = select_multiple("Select task sources", options)
            for idx in selected_indices:
                if option_keys[idx] != "none":
                    selected_sources.append(option_keys[idx])

        print()
        print(f"Selected sources: {', '.join(selected_sources) if selected_sources else 'none'}")

    # Phase 3: Configuration
    print_header("Configuration", "Phase 3 of 5")

    # Project name
    if non_interactive:
        config_project_name = context["name"]
    else:
        config_project_name = prompt_text("Project name", context["name"])

    # API call limit
    if non_interactive:
        config_max_calls = 100
    else:
        config_max_calls = prompt_number("Max API calls per hour", 100, 10, 500)

    # GitHub label
    config_github_label = label or "ralph-task"
    if "github" in selected_sources and non_interactive:
        pass  # Use default
    elif "github" in selected_sources and not non_interactive:
        config_github_label = prompt_text("GitHub issue label filter", "ralph-task")

    # PRD file
    config_prd_file = prd_file
    if "prd" in selected_sources:
        if config_prd_file:
            pass  # Use provided
        elif task_sources["prd_files"] and not non_interactive:
            config_prd_file = select_option("Select PRD file to convert", task_sources["prd_files"])
        elif task_sources["prd_files"]:
            config_prd_file = task_sources["prd_files"][0]
        else:
            config_prd_file = None

    # Phase 4: File Generation
    print_header("File Generation", "Phase 4 of 5")

    # Import tasks
    imported_tasks = []

    if selected_sources and not skip_tasks:
        print("Importing tasks...")

        if "beads" in selected_sources:
            beads_tasks = fetch_beads_tasks()
            if beads_tasks:
                imported_tasks.append(beads_tasks)
                print_success("Imported tasks from beads")

        if "github" in selected_sources:
            github_tasks = fetch_github_tasks(config_github_label)
            if github_tasks:
                imported_tasks.append(github_tasks)
                print_success("Imported tasks from GitHub")

        if "prd" in selected_sources and config_prd_file:
            prd_tasks = extract_prd_tasks(Path(config_prd_file))
            if prd_tasks:
                imported_tasks.append(prd_tasks)
                print_success(f"Extracted tasks from PRD: {config_prd_file}")

        print()

    # Create Ralph configuration
    print("Creating Ralph configuration...")
    print()

    task_content = "\n".join(imported_tasks)

    if not enable_ralph_in_directory(
        project_path,
        config_project_name,
        context["type"],
        context["framework"],
        context["build_cmd"],
        context["test_cmd"],
        context["run_cmd"],
        task_content,
        force
    ):
        print_error("Failed to enable Ralph")
        sys.exit(ENABLE_ERROR)

    # Phase 5: Verification
    print_header("Verification", "Phase 5 of 5")

    print("Checking created files...")
    print()

    all_good = True

    for file in [".ralph/PROMPT.md", ".ralph/fix_plan.md", ".ralph/AGENT.md", ".ralphrc"]:
        if (project_path / file).exists():
            print_success(file)
        else:
            print_error(f"{file} - MISSING")
            all_good = False

    if (project_path / ".ralph" / "specs").exists():
        print_success(".ralph/specs/")

    if (project_path / ".ralph" / "logs").exists():
        print_success(".ralph/logs/")

    print()

    if all_good:
        print_success("Ralph enabled successfully!")
        print()
        print("Next steps:")
        print()
        print(f"  {CYAN}1.{NC} Review and customize .ralph/PROMPT.md")
        print(f"  {CYAN}2.{NC} Edit tasks in .ralph/fix_plan.md")
        print(f"  {CYAN}3.{NC} Update build commands in .ralph/AGENT.md")
        print(f"  {CYAN}4.{NC} Start Ralph: ralph --monitor")
        print()
    else:
        print_error("Some files were not created. Please check the errors above.")
        sys.exit(ENABLE_ERROR)

    sys.exit(ENABLE_SUCCESS)


if __name__ == "__main__":
    enable()

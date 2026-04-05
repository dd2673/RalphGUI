#!/usr/bin/env python3
"""
enable_core.py - Shared logic for Ralph enable commands

Provides:
- Idempotency checks
- Safe file operations
- Project detection
- Template generation

Used by:
    - ralph_enable (interactive wizard)
    - ralph_enable_ci (non-interactive CI version)
"""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Exit codes
ENABLE_SUCCESS = 0
ENABLE_ERROR = 1
ENABLE_ALREADY_ENABLED = 2
ENABLE_INVALID_ARGS = 3
ENABLE_FILE_NOT_FOUND = 4
ENABLE_DEPENDENCY_MISSING = 5
ENABLE_PERMISSION_DENIED = 6

# Colors (can be disabled for non-interactive mode)
USE_COLORS = True

# Color codes
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
NC = '\033[0m'


def _log(level: str, message: str) -> None:
    """Log a message with level prefix."""
    color = ""
    if USE_COLORS:
        color_map = {
            "INFO": BLUE,
            "WARN": YELLOW,
            "ERROR": RED,
            "SUCCESS": GREEN,
            "SKIP": CYAN
        }
        color = color_map.get(level, "")

    if color:
        print(f"{color}[{level}]{NC} {message}")
    else:
        print(f"[{level}] {message}")


# =============================================================================
# IDEMPOTENCY CHECKS
# =============================================================================

def check_existing_ralph(project_dir: str = ".") -> Tuple[int, List[str]]:
    """
    Check if .ralph directory exists and its state.

    Args:
        project_dir: Project directory to check (default: ".")

    Returns:
        Tuple of (state_code, missing_files_list):
        - state_code 0: No .ralph directory, safe to proceed
        - state_code 1: .ralph exists but incomplete (partial setup)
        - state_code 2: .ralph exists and fully initialized
        - missing_files_list: List of missing required files if partial
    """
    ralph_dir = os.path.join(project_dir, ".ralph")

    if not os.path.isdir(ralph_dir):
        return 0, []

    # Check for required files
    required_files = [
        os.path.join(ralph_dir, "PROMPT.md"),
        os.path.join(ralph_dir, "fix_plan.md"),
        os.path.join(ralph_dir, "AGENT.md"),
    ]

    missing = []
    found = 0

    for file_path in required_files:
        if os.path.isfile(file_path):
            found += 1
        else:
            missing.append(file_path)

    if found == 0:
        return 0, missing
    elif missing:
        return 1, missing
    else:
        return 2, []


def is_ralph_enabled(project_dir: str = ".") -> bool:
    """
    Simple check if Ralph is fully enabled.

    Args:
        project_dir: Project directory to check (default: ".")

    Returns:
        True if Ralph is fully enabled.
    """
    state_code, _ = check_existing_ralph(project_dir)
    return state_code == 2


# =============================================================================
# SAFE FILE OPERATIONS
# =============================================================================

def safe_create_file(
    file_path: str,
    content: str,
    mode: int = 0o600,
    force: bool = False
) -> Tuple[bool, str]:
    """
    Create a file only if it doesn't exist (or force overwrite).

    Args:
        file_path: Target file path
        content: Content to write (can be empty string)
        mode: File permissions (default: 0o600)
        force: If True, overwrite existing files

    Returns:
        Tuple of (success, status_message).
    """
    if os.path.isfile(file_path):
        if force:
            _log("INFO", f"Overwriting {file_path} (--force)")
        else:
            _log("SKIP", f"{file_path} already exists")
            return False, "skipped"

    # Create parent directory if needed
    parent_dir = os.path.dirname(file_path)
    if parent_dir and not os.path.isdir(parent_dir):
        try:
            os.makedirs(parent_dir, exist_ok=True)
        except OSError as e:
            _log("ERROR", f"Failed to create directory: {parent_dir}")
            return False, "error"

    # Write content to file
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Set file permissions
        os.chmod(file_path, mode)

        if force:
            _log("SUCCESS", f"Overwrote {file_path}")
        else:
            _log("SUCCESS", f"Created {file_path}")

        return True, "created"

    except OSError as e:
        _log("ERROR", f"Failed to create: {file_path}")
        return False, "error"


def safe_create_dir(dir_path: str) -> bool:
    """
    Create a directory only if it doesn't exist.

    Args:
        dir_path: Target directory path

    Returns:
        True if directory was created or already exists.
    """
    if os.path.isdir(dir_path):
        return True

    try:
        os.makedirs(dir_path, exist_ok=True)
        _log("SUCCESS", f"Created directory: {dir_path}")
        return True
    except OSError as e:
        _log("ERROR", f"Failed to create directory: {dir_path}")
        return False


# =============================================================================
# DIRECTORY STRUCTURE
# =============================================================================

def create_ralph_structure(project_dir: str = ".") -> bool:
    """
    Create the .ralph/ directory structure.

    Creates:
        .ralph/
        .ralph/specs/
        .ralph/examples/
        .ralph/logs/
        .ralph/docs/generated/

    Args:
        project_dir: Project directory (default: ".")

    Returns:
        True if structure created successfully.
    """
    dirs = [
        os.path.join(project_dir, ".ralph"),
        os.path.join(project_dir, ".ralph", "specs"),
        os.path.join(project_dir, ".ralph", "examples"),
        os.path.join(project_dir, ".ralph", "logs"),
        os.path.join(project_dir, ".ralph", "docs", "generated"),
    ]

    for dir_path in dirs:
        if not safe_create_dir(dir_path):
            return False

    return True


# =============================================================================
# PROJECT DETECTION
# =============================================================================

def detect_project_context(project_dir: str = ".") -> Dict:
    """
    Detect project type, name, and build commands.

    Detects:
        - Project type: javascript, typescript, python, rust, go, unknown
        - Framework: nextjs, fastapi, express, etc.
        - Build/test/run commands based on detected tooling

    Args:
        project_dir: Project directory (default: ".")

    Returns:
        Dictionary with detected project information:
        - project_name: Project name
        - project_type: Language/type
        - framework: Framework if detected
        - build_cmd: Build command
        - test_cmd: Test command
        - run_cmd: Run/start command
    """
    result = {
        "project_name": "",
        "project_type": "unknown",
        "framework": "",
        "build_cmd": "",
        "test_cmd": "",
        "run_cmd": "",
    }

    original_dir = os.getcwd()
    try:
        if project_dir != ".":
            os.chdir(project_dir)

        # Detect from package.json (JavaScript/TypeScript)
        if os.path.isfile("package.json"):
            result["project_type"] = "javascript"

            # Check for TypeScript
            try:
                with open("package.json", "r", encoding="utf-8") as f:
                    pkg_data = json.load(f)

                # Check for TypeScript
                if "typescript" in pkg_data.get("dependencies", {}) or \
                   "typescript" in pkg_data.get("devDependencies", {}) or \
                   os.path.isfile("tsconfig.json"):
                    result["project_type"] = "typescript"

                # Extract project name
                result["project_name"] = pkg_data.get("name", "")

                # Detect framework
                deps = {**pkg_data.get("dependencies", {}),
                       **pkg_data.get("devDependencies", {})}

                if "next" in deps:
                    result["framework"] = "nextjs"
                elif "express" in deps:
                    result["framework"] = "express"
                elif "react" in deps:
                    result["framework"] = "react"
                elif "vue" in deps:
                    result["framework"] = "vue"
            except (json.JSONDecodeError, IOError):
                pass

            # Set build commands
            result["build_cmd"] = "npm run build"
            result["test_cmd"] = "npm test"
            result["run_cmd"] = "npm start"

            # Check for yarn
            if os.path.isfile("yarn.lock"):
                result["build_cmd"] = "yarn build"
                result["test_cmd"] = "yarn test"
                result["run_cmd"] = "yarn start"

            # Check for pnpm
            if os.path.isfile("pnpm-lock.yaml"):
                result["build_cmd"] = "pnpm build"
                result["test_cmd"] = "pnpm test"
                result["run_cmd"] = "pnpm start"

        # Detect from pyproject.toml or setup.py (Python)
        if os.path.isfile("pyproject.toml") or os.path.isfile("setup.py"):
            result["project_type"] = "python"

            # Extract project name from pyproject.toml
            if os.path.isfile("pyproject.toml"):
                try:
                    with open("pyproject.toml", "r", encoding="utf-8") as f:
                        content = f.read()

                    name_match = re.search(r'^name\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
                    if name_match:
                        result["project_name"] = name_match.group(1)

                    if "fastapi" in content:
                        result["framework"] = "fastapi"
                    elif "django" in content:
                        result["framework"] = "django"
                    elif "flask" in content:
                        result["framework"] = "flask"
                except IOError:
                    pass

            # Set build commands (prefer uv if detected)
            if os.path.isfile("uv.lock") or _command_exists("uv"):
                result["build_cmd"] = "uv sync"
                result["test_cmd"] = "uv run pytest"
                result["run_cmd"] = f"uv run python -m {result['project_name'] or 'main'}"
            else:
                result["build_cmd"] = "pip install -e ."
                result["test_cmd"] = "pytest"
                result["run_cmd"] = f"python -m {result['project_name'] or 'main'}"

        # Detect from Cargo.toml (Rust)
        if os.path.isfile("Cargo.toml"):
            result["project_type"] = "rust"
            result["build_cmd"] = "cargo build"
            result["test_cmd"] = "cargo test"
            result["run_cmd"] = "cargo run"

            try:
                with open("Cargo.toml", "r", encoding="utf-8") as f:
                    content = f.read()
                name_match = re.search(r'^name\s*=\s*"([^"]+)"', content, re.MULTILINE)
                if name_match:
                    result["project_name"] = name_match.group(1)
            except IOError:
                pass

        # Detect from go.mod (Go)
        if os.path.isfile("go.mod"):
            result["project_type"] = "go"
            result["build_cmd"] = "go build"
            result["test_cmd"] = "go test ./..."
            result["run_cmd"] = "go run ."

            try:
                with open("go.mod", "r", encoding="utf-8") as f:
                    first_line = f.readline().strip()
                if first_line.startswith("module "):
                    result["project_name"] = first_line[7:]
            except IOError:
                pass

        # Fallback project name to folder name
        if not result["project_name"]:
            result["project_name"] = os.path.basename(os.getcwd())

    finally:
        if project_dir != ".":
            os.chdir(original_dir)

    return result


def _command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    try:
        subprocess.run(
            [cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def detect_git_info(project_dir: str = ".") -> Dict:
    """
    Detect git repository information.

    Args:
        project_dir: Project directory (default: ".")

    Returns:
        Dictionary with git information:
        - is_repo: bool
        - remote_url: str
        - is_github: bool
    """
    result = {
        "is_repo": False,
        "remote_url": "",
        "is_github": False,
    }

    original_dir = os.getcwd()
    try:
        if project_dir != ".":
            os.chdir(project_dir)

        # Check if in git repo
        try:
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                timeout=5
            )
            result["is_repo"] = True

            # Get remote URL
            proc = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if proc.returncode == 0:
                result["remote_url"] = proc.stdout.strip()
                result["is_github"] = "github.com" in result["remote_url"]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    finally:
        if project_dir != ".":
            os.chdir(original_dir)

    return result


def detect_task_sources(project_dir: str = ".") -> Dict:
    """
    Detect available task sources.

    Args:
        project_dir: Project directory (default: ".")

    Returns:
        Dictionary with task source information:
        - beads_available: bool
        - github_available: bool
        - prd_files: list of potential PRD files
    """
    result = {
        "beads_available": False,
        "github_available": False,
        "prd_files": [],
    }

    original_dir = os.getcwd()
    try:
        if project_dir != ".":
            os.chdir(project_dir)

        # Check for beads
        if os.path.isdir(".beads"):
            result["beads_available"] = True

        # Check for GitHub
        git_info = detect_git_info()
        result["github_available"] = git_info["is_github"]

        # Search for PRD/spec files
        search_dirs = ["docs", "specs", ".", "requirements"]
        prd_patterns = ["*prd*.md", "*PRD*.md", "*requirements*.md",
                       "*spec*.md", "*specification*.md"]

        for search_dir in search_dirs:
            if not os.path.isdir(search_dir):
                continue

            for pattern in prd_patterns:
                path = Path(search_dir)
                for file_path in path.glob(pattern):
                    if file_path.is_file():
                        result["prd_files"].append(str(file_path))

    finally:
        if project_dir != ".":
            os.chdir(original_dir)

    return result


# =============================================================================
# TEMPLATE GENERATION
# =============================================================================

def get_templates_dir() -> Optional[str]:
    """
    Get the templates directory path.

    Returns:
        Path to templates directory, or None if not found.
    """
    # Check global installation first
    home_templates = os.path.join(os.path.expanduser("~"), ".ralph", "templates")
    if os.path.isdir(home_templates):
        return home_templates

    # Check local installation (development)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_templates = os.path.join(script_dir, "..", "templates")
    if os.path.isdir(local_templates):
        return local_templates

    return None


def generate_prompt_md(
    project_name: str = "",
    project_type: str = "unknown",
    framework: str = "",
    objectives: str = ""
) -> str:
    """
    Generate PROMPT.md with project context.

    Args:
        project_name: Project name
        project_type: Project type (typescript, python, etc.)
        framework: Framework if any
        objectives: Custom objectives (newline-separated)

    Returns:
        Content for PROMPT.md file.
    """
    if not project_name:
        project_name = os.path.basename(os.getcwd())

    framework_line = ""
    if framework:
        framework_line = f"**Framework:** {framework}"

    if not objectives:
        objectives_section = """- Review the codebase and understand the current state
- Follow tasks in fix_plan.md
- Implement one task per loop
- Write tests for new functionality
- Update documentation as needed"""
    else:
        objectives_section = objectives

    return f"""# Ralph Development Instructions

## Context
You are Ralph, an autonomous AI development agent working on the **{project_name}** project.

**Project Type:** {project_type}
{framework_line}

## Current Objectives
{objectives_section}

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


def generate_agent_md(
    build_cmd: str = "echo 'No build command configured'",
    test_cmd: str = "echo 'No test command configured'",
    run_cmd: str = "echo 'No run command configured'"
) -> str:
    """
    Generate AGENT.md with detected build commands.

    Args:
        build_cmd: Build command
        test_cmd: Test command
        run_cmd: Run command

    Returns:
        Content for AGENT.md file.
    """
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
    """
    Generate fix_plan.md with imported tasks.

    Args:
        tasks: Tasks to include (newline-separated, markdown checkbox format)

    Returns:
        Content for fix_plan.md file.
    """
    high_priority = tasks if tasks else """- [ ] Review codebase and understand architecture
- [ ] Identify and document key components
- [ ] Set up development environment"""

    medium_priority = """- [ ] Implement core features
- [ ] Add test coverage
- [ ] Update documentation"""

    low_priority = """- [ ] Performance optimization
- [ ] Code cleanup and refactoring"""

    return f"""# Ralph Fix Plan

## High Priority
{high_priority}

## Medium Priority
{medium_priority}

## Low Priority
{low_priority}

## Completed
- [x] Project enabled for Ralph

## Notes
- Focus on MVP functionality first
- Ensure each feature is properly tested
- Update this file after each major milestone
"""


def generate_ralphrc(
    project_name: str = "",
    project_type: str = "unknown",
    task_sources: str = "local"
) -> str:
    """
    Generate .ralphrc configuration file.

    Args:
        project_name: Project name
        project_type: Project type
        task_sources: Task sources (local, beads, github)

    Returns:
        Content for .ralphrc file.
    """
    if not project_name:
        project_name = os.path.basename(os.getcwd())

    # Auto-detect Claude Code CLI command
    claude_cmd = "claude"
    if not _command_exists("claude"):
        if _command_exists("npx"):
            claude_cmd = "npx @anthropic-ai/claude-code"

    return f"""# .ralphrc - Ralph project configuration
# Generated by: ralph enable
# Documentation: https://github.com/frankbria/ralph-claude-code

# Project identification
PROJECT_NAME="{project_name}"
PROJECT_TYPE="{project_type}"

# Claude Code CLI command
# If "claude" is not in your PATH, set to your installation:
#   "npx @anthropic-ai/claude-code"  (uses npx, no global install needed)
#   "/path/to/claude"                (custom path)
CLAUDE_CODE_CMD="{claude_cmd}"

# Loop settings
MAX_CALLS_PER_HOUR=100
CLAUDE_TIMEOUT_MINUTES=15
CLAUDE_OUTPUT_FORMAT="json"
# Token limit per hour (0 = disabled). One invocation can use 100k+ tokens.
# Recommended: 500000 for light use, 2000000 for heavy use.
#MAX_TOKENS_PER_HOUR=0

# Tool permissions
# Comma-separated list of allowed tools
# Safe git subcommands only - broad Bash(git *) allows destructive commands like git clean/git rm (Issue #149)
ALLOWED_TOOLS="Write,Read,Edit,Bash(git add *),Bash(git commit *),Bash(git diff *),Bash(git log *),Bash(git status),Bash(git status *),Bash(git push *),Bash(git pull *),Bash(git fetch *),Bash(git checkout *),Bash(git branch *),Bash(git stash *),Bash(git merge *),Bash(git tag *),Bash(npm *),Bash(pytest)"

# Session management
SESSION_CONTINUITY=true
SESSION_EXPIRY_HOURS=24

# Task sources (for ralph enable --sync)
# Options: local, beads, github (comma-separated for multiple)
TASK_SOURCES="{task_sources}"
GITHUB_TASK_LABEL="ralph-task"
BEADS_FILTER="status:open"

# Circuit breaker thresholds
CB_NO_PROGRESS_THRESHOLD=3
CB_SAME_ERROR_THRESHOLD=5
CB_OUTPUT_DECLINE_THRESHOLD=70

# Auto-update Claude CLI at startup
CLAUDE_AUTO_UPDATE=true

# Shell init file (optional)
# Source this file before running claude — useful when claude requires environment
# variables or PATH entries defined in a non-bash shell config (e.g. ~/.zshrc).
# Leave commented out unless needed.
#RALPH_SHELL_INIT_FILE="~/.zshrc"
"""


# =============================================================================
# MAIN ENABLE LOGIC
# =============================================================================

def enable_ralph_in_directory(
    project_dir: str = ".",
    force: bool = False,
    skip_tasks: bool = False,
    project_name: str = "",
    project_type: str = "",
    task_content: str = ""
) -> Tuple[int, str]:
    """
    Main function to enable Ralph in a directory.

    Args:
        project_dir: Target project directory
        force: Force overwrite existing
        skip_tasks: Skip task import
        project_name: Override project name
        project_type: Override project type
        task_content: Pre-imported task content

    Returns:
        Tuple of (exit_code, message).
    """
    # Check existing state
    state_code, missing_files = check_existing_ralph(project_dir)

    if state_code == 2 and not force:
        _log("INFO", "Ralph is already enabled in this project")
        _log("INFO", "Use --force to overwrite existing configuration")
        return ENABLE_ALREADY_ENABLED, "already_enabled"

    # Detect project context
    context = detect_project_context(project_dir)

    # Use detected or provided project name
    if not project_name:
        project_name = context["project_name"]

    # Use detected or provided project type
    if project_type:
        context["project_type"] = project_type

    _log("INFO", f"Enabling Ralph for: {project_name}")
    _log("INFO", f"Project type: {context['project_type']}")
    if context["framework"]:
        _log("INFO", f"Framework: {context['framework']}")

    # Create directory structure
    if not create_ralph_structure(project_dir):
        _log("ERROR", "Failed to create .ralph/ structure")
        return ENABLE_ERROR, "structure_error"

    # Generate and create files
    prompt_content = generate_prompt_md(
        project_name,
        context["project_type"],
        context["framework"]
    )
    safe_create_file(
        os.path.join(project_dir, ".ralph", "PROMPT.md"),
        prompt_content,
        force=force
    )

    agent_content = generate_agent_md(
        context["build_cmd"],
        context["test_cmd"],
        context["run_cmd"]
    )
    safe_create_file(
        os.path.join(project_dir, ".ralph", "AGENT.md"),
        agent_content,
        force=force
    )

    fix_plan_content = generate_fix_plan_md(task_content)
    safe_create_file(
        os.path.join(project_dir, ".ralph", "fix_plan.md"),
        fix_plan_content,
        force=force
    )

    # Copy .gitignore template if available
    templates_dir = get_templates_dir()
    if templates_dir:
        gitignore_template = os.path.join(templates_dir, ".gitignore")
        if os.path.isfile(gitignore_template):
            try:
                with open(gitignore_template, "r", encoding="utf-8") as f:
                    gitignore_content = f.read()
                safe_create_file(
                    os.path.join(project_dir, ".gitignore"),
                    gitignore_content,
                    force=force
                )
            except IOError:
                pass
        else:
            _log("WARN", ".gitignore template not found, skipping")
    else:
        _log("WARN", "Templates directory not found, skipping .gitignore")

    # Detect task sources for .ralphrc
    task_sources_info = detect_task_sources(project_dir)
    task_sources = "local"
    if task_sources_info["beads_available"]:
        task_sources = f"beads,{task_sources}"
    if task_sources_info["github_available"]:
        task_sources = f"github,{task_sources}"

    # Generate .ralphrc
    ralphrc_content = generate_ralphrc(project_name, context["project_type"], task_sources)
    safe_create_file(
        os.path.join(project_dir, ".ralphrc"),
        ralphrc_content,
        force=force
    )

    _log("SUCCESS", "Ralph enabled successfully!")

    return ENABLE_SUCCESS, "success"

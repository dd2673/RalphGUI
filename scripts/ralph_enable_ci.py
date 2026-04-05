#!/usr/bin/env python3
"""
Ralph Enable CI - Non-Interactive Version for Automation

Adds Ralph configuration with sensible defaults for CI/automation use.
"""

import os
import sys
import click
from pathlib import Path
from typing import Optional, List, Dict, Any
import subprocess
import json


# Exit codes
ENABLE_SUCCESS = 0
ENABLE_ERROR = 1
ENABLE_ALREADY_ENABLED = 2
ENABLE_INVALID_ARGS = 3
ENABLE_FILE_NOT_FOUND = 4
ENABLE_DEPENDENCY_MISSING = 5


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
                    for line in content.split("\n"):
                        if line.startswith("name"):
                            result["name"] = line.split("=")[1].strip().strip('"').strip("'")
                            break
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
        result["repo"] = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=project_dir,
            capture_output=True,
            timeout=5
        ).returncode == 0

        if result["repo"]:
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

    if (project_dir / ".beads").is_dir():
        result["beads_available"] = True

    git_info = detect_git_info(project_dir)
    result["github_available"] = git_info["github"]

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
# Generated by: ralph enable-ci

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
            import re
            if re.match(r'^[\s]*[-*][\s]*\[[\s]*[xX ]?[\s]*\]', line):
                line = re.sub(r'\[x\]', '[ ]', line, flags=re.IGNORECASE)
                lines.append(line)
            elif re.match(r'^[\s]*[0-9]+\.[\s]+', line):
                task_text = re.sub(r'^[\s]*[0-9]*\.[\s]*', '', line)
                lines.append(f"- [ ] {task_text}")

        return "\n".join(lines[:30])
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
    create_ralph_structure(project_dir)

    prompt_content = generate_prompt_md(project_name, project_type, framework)
    safe_create_file(project_dir / ".ralph" / "PROMPT.md", prompt_content, force)

    agent_content = generate_agent_md(build_cmd, test_cmd, run_cmd)
    safe_create_file(project_dir / ".ralph" / "AGENT.md", agent_content, force)

    fix_plan_content = generate_fix_plan_md(task_content)
    safe_create_file(project_dir / ".ralph" / "fix_plan.md", fix_plan_content, force)

    task_sources = "local"
    ralphrc_content = generate_ralphrc(project_name, project_type, task_sources)
    safe_create_file(project_dir / ".ralphrc", ralphrc_content, force)

    return True


# =============================================================================
# CLI COMMAND
# =============================================================================

@click.command()
@click.option("--project-dir", default=".", help="Project directory")
@click.option("--project-type", help="Override detected type (typescript, python, etc.)")
@click.option("--from-source", help="Import tasks from: beads, github, prd, none")
@click.option("--prd", "prd_file", help="PRD file to convert (when --from prd)")
@click.option("--label", default="ralph-task", help="GitHub label filter")
@click.option("--project-name", help="Override detected project name")
@click.option("--force", is_flag=True, help="Overwrite existing .ralph/ configuration")
@click.option("--json", "output_json", is_flag=True, help="Output result as JSON")
@click.option("--quiet", is_flag=True, help="Suppress non-error output")
def enable_ci(
    project_dir: str = ".",
    project_type: Optional[str] = None,
    from_source: Optional[str] = None,
    prd_file: Optional[str] = None,
    label: str = "ralph-task",
    project_name: Optional[str] = None,
    force: bool = False,
    output_json: bool = False,
    quiet: bool = False
) -> None:
    """
    Non-interactive enable Ralph (for CI/automation).

    Exit codes:
        0 - Success: Ralph enabled
        1 - Error: General error
        2 - Already enabled: Use --force to override
        3 - Invalid arguments
        4 - File not found (e.g., PRD file)
        5 - Dependency missing (e.g., jq for --json)
    """
    project_path = Path(project_dir).resolve()

    if not output_json and not quiet:
        print("Ralph Enable CI - Non-Interactive Mode")
        print()

    # Check existing state
    state, _ = check_existing_ralph(project_path)
    if state == "complete" and not force:
        if output_json:
            print(json.dumps({"success": False, "code": 2, "message": "Ralph already enabled. Use --force to override."}))
        else:
            print("Ralph is already enabled in this project. Use --force to override.")
        sys.exit(ENABLE_ALREADY_ENABLED)

    # Detect project context
    context = detect_project_context(project_path)

    if project_name:
        context["name"] = project_name
    if project_type:
        context["type"] = project_type

    if not quiet:
        print(f"Detected: {context['name']} ({context['type']})")

    # Auto-detect task source if not specified
    task_source = from_source
    if not task_source:
        task_sources = detect_task_sources(project_path)

        if task_sources["beads_available"]:
            task_source = "beads"
            if not quiet:
                print(f"Auto-detected task source: beads")
        elif task_sources["github_available"]:
            task_source = "github"
            if not quiet:
                print(f"Auto-detected task source: github")
        elif task_sources["prd_files"]:
            task_source = "prd"
            prd_file = task_sources["prd_files"][0]
            if not quiet:
                print(f"Auto-detected task source: prd ({prd_file})")
        else:
            task_source = "none"
            if not quiet:
                print("No task sources detected, using defaults")

    # Import tasks
    imported_tasks = ""
    tasks_imported = 0

    if task_source == "beads":
        beads_tasks = fetch_beads_tasks()
        if beads_tasks:
            imported_tasks = beads_tasks
            tasks_imported = beads_tasks.count("\n") + 1
            if not quiet:
                print(f"Imported {tasks_imported} tasks from beads")

    elif task_source == "github":
        github_tasks = fetch_github_tasks(label)
        if github_tasks:
            imported_tasks = github_tasks
            tasks_imported = github_tasks.count("\n") + 1
            if not quiet:
                print(f"Imported {tasks_imported} tasks from GitHub")

    elif task_source == "prd":
        if not prd_file:
            if output_json:
                print(json.dumps({"error": f"PRD file not specified", "code": 4}))
            else:
                print(f"Error: PRD file not specified")
            sys.exit(ENABLE_FILE_NOT_FOUND)

        prd_path = Path(prd_file)
        if not prd_path.exists():
            if output_json:
                print(json.dumps({"error": f"PRD file not found: {prd_file}", "code": 4}))
            else:
                print(f"Error: PRD file not found: {prd_file}")
            sys.exit(ENABLE_FILE_NOT_FOUND)

        prd_tasks = extract_prd_tasks(prd_path)
        if prd_tasks:
            imported_tasks = prd_tasks
            tasks_imported = prd_tasks.count("\n") + 1
            if not quiet:
                print(f"Extracted {tasks_imported} tasks from PRD")

    elif task_source == "none" or not task_source:
        if not quiet:
            print("Skipping task import")

    # Create Ralph configuration
    if not quiet:
        print()
        print("Creating Ralph configuration...")

    success = enable_ralph_in_directory(
        project_path,
        context["name"],
        context["type"],
        context["framework"],
        context["build_cmd"],
        context["test_cmd"],
        context["run_cmd"],
        imported_tasks,
        force
    )

    if not success:
        if output_json:
            print(json.dumps({"success": False, "code": 1, "message": "Failed to enable Ralph"}))
        else:
            print("Error: Failed to enable Ralph")
        sys.exit(ENABLE_ERROR)

    # Track created files
    created_files = []
    for file in [".ralph/PROMPT.md", ".ralph/fix_plan.md", ".ralph/AGENT.md", ".ralphrc"]:
        if (project_path / file).exists():
            created_files.append(file)

    # Verify required files exist
    if not (project_path / ".ralph/PROMPT.md").exists() or not (project_path / ".ralph/fix_plan.md").exists():
        if output_json:
            print(json.dumps({"success": False, "code": 1, "message": "Required files were not created"}))
        else:
            print("Error: Required files were not created")
        sys.exit(ENABLE_ERROR)

    # Output success
    if output_json:
        print(json.dumps({
            "success": True,
            "project_name": context["name"],
            "project_type": context["type"],
            "files_created": created_files,
            "tasks_imported": tasks_imported,
            "message": "Ralph enabled successfully"
        }))
    else:
        print()
        print("Ralph enabled successfully!")
        print(f"Project: {context['name']} ({context['type']})")
        print(f"Files created: {len(created_files)}")
        print(f"Tasks imported: {tasks_imported}")

    sys.exit(ENABLE_SUCCESS)


if __name__ == "__main__":
    enable_ci()

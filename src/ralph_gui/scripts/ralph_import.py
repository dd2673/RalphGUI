#!/usr/bin/env python3
"""
Ralph Import - Convert PRDs to Ralph format using Claude Code.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


# Configuration
CLAUDE_CODE_CMD = "claude"
CLAUDE_OUTPUT_FORMAT = "json"
CLAUDE_MIN_VERSION = "2.0.76"

# Temporary file names
CONVERSION_OUTPUT_FILE = ".ralph_conversion_output.json"
CONVERSION_PROMPT_FILE = ".ralph_conversion_prompt.md"


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


def detect_response_format(output_file: Path) -> str:
    """Detect whether file contains JSON or plain text output."""
    if not output_file.exists() or output_file.stat().st_size == 0:
        return "text"

    # Check if file starts with { or [
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            first_char = None
            for line in f:
                line = line.strip()
                if line:
                    first_char = line[0]
                    break

        if first_char not in ("{", "["):
            return "text"

        # Validate as JSON using json module
        with open(output_file, "r", encoding="utf-8") as f:
            json.load(f)
        return "json"
    except (json.JSONDecodeError, UnicodeDecodeError):
        return "text"


def check_claude_version() -> bool:
    """Check Claude Code CLI version meets minimum requirements."""
    try:
        result = subprocess.run(
            [CLAUDE_CODE_CMD, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        output = result.stdout + result.stderr

        # Extract version number
        import re
        match = re.search(r'(\d+)\.(\d+)\.(\d+)', output)
        if not match:
            log("WARN", "Could not determine Claude Code CLI version")
            return False

        ver_major, ver_minor, ver_patch = map(int, match.groups())

        # Compare with minimum version
        min_major, min_minor, min_patch = map(int, CLAUDE_MIN_VERSION.split("."))

        if ver_major < min_major:
            log("WARN", f"Claude Code CLI version {ver_major}.{ver_minor}.{ver_patch} is below recommended {CLAUDE_MIN_VERSION}")
            return False
        if ver_major == min_major and ver_minor < min_minor:
            log("WARN", f"Claude Code CLI version {ver_major}.{ver_minor}.{ver_patch} is below recommended {CLAUDE_MIN_VERSION}")
            return False
        if ver_major == min_major and ver_minor == min_minor and ver_patch < min_patch:
            log("WARN", f"Claude Code CLI version {ver_major}.{ver_minor}.{ver_patch} is below recommended {CLAUDE_MIN_VERSION}")
            return False

        return True
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log("WARN", f"Could not check Claude Code CLI version: {e}")
        return False


def check_dependencies() -> bool:
    """Check required dependencies."""
    # Check for ralph-setup
    if not shutil.which("ralph-setup"):
        # Try to find it in the same directory as this script
        script_dir = Path(__file__).parent
        local_setup = script_dir / "ralph_setup.py"
        if local_setup.exists():
            pass  # We can call it directly
        else:
            log("ERROR", "Ralph not installed. Run install.sh first or ensure ralph-setup is in PATH.")
            return False

    # Check for Claude Code CLI
    if not shutil.which(CLAUDE_CODE_CMD):
        log("WARN", f"Claude Code CLI ({CLAUDE_CODE_CMD}) not found. It will be downloaded when first used.")

    return True


def create_conversion_prompt(source_file: Path) -> str:
    """Create the conversion prompt for Claude Code."""
    prompt = """# PRD to Ralph Conversion Task

You are tasked with converting a Product Requirements Document (PRD) or specification into Ralph for Claude Code format.

## Input Analysis
Analyze the provided specification file and extract:
- Project goals and objectives
- Core features and requirements
- Technical constraints and preferences
- Priority levels and phases
- Success criteria

## Required Outputs

Create these files in the .ralph/ subdirectory:

### 1. .ralph/PROMPT.md
Transform the PRD into Ralph development instructions:
```markdown
# Ralph Development Instructions

## Context
You are Ralph, an autonomous AI development agent working on a [PROJECT NAME] project.

## Current Objectives
[Extract and prioritize 4-6 main objectives from the PRD]

## Key Principles
- ONE task per loop - focus on the most important thing
- Search the codebase before assuming something isn't implemented
- Use subagents for expensive operations (file searching, analysis)
- Write comprehensive tests with clear documentation
- Update fix_plan.md with your learnings
- Commit working changes with descriptive messages

## Testing Guidelines (CRITICAL)
- LIMIT testing to ~20% of your total effort per loop
- PRIORITIZE: Implementation > Documentation > Tests
- Only write tests for NEW functionality you implement
- Do NOT refactor existing tests unless broken
- Focus on CORE functionality first, comprehensive testing later

## Project Requirements
[Convert PRD requirements into clear, actionable development requirements]

## Technical Constraints
[Extract any technical preferences, frameworks, languages mentioned]

## Success Criteria
[Define what "done" looks like based on the PRD]

## Current Task
Follow fix_plan.md and choose the most important item to implement next.
```

### 2. .ralph/fix_plan.md
Convert requirements into a prioritized task list:
```markdown
# Ralph Fix Plan

## High Priority
[Extract and convert critical features into actionable tasks]

## Medium Priority
[Secondary features and enhancements]

## Low Priority
[Nice-to-have features and optimizations]

## Completed
- [x] Project initialization

## Notes
[Any important context from the original PRD]
```

### 3. .ralph/specs/requirements.md
Create detailed technical specifications:
```markdown
# Technical Specifications

[Convert PRD into detailed technical requirements including:]
- System architecture requirements
- Data models and structures
- API specifications
- User interface requirements
- Performance requirements
- Security considerations
- Integration requirements

[Preserve all technical details from the original PRD]
```

## Instructions
1. Read and analyze the attached specification file
2. Create the three files above with content derived from the PRD
3. Ensure all requirements are captured and properly prioritized
4. Make the PROMPT.md actionable for autonomous development
5. Structure fix_plan.md with clear, implementable tasks

"""
    return prompt


def convert_prd(source_file: Path, project_name: str, output_file: Path = None) -> bool:
    """Convert PRD using Claude Code."""
    log("INFO", "Converting PRD to Ralph format using Claude Code...")

    use_modern_cli = check_claude_version()
    if use_modern_cli:
        log("INFO", "Using modern CLI with JSON output format")
    else:
        log("INFO", "Using standard CLI mode (modern features may not be available)")

    # Create conversion prompt
    prompt = create_conversion_prompt(source_file)

    # Read source file content
    try:
        source_content = source_file.read_text(encoding="utf-8")
    except Exception as e:
        log("ERROR", f"Failed to read source file: {e}")
        return False

    # Append source content to prompt
    prompt += f"""
---

## Source PRD File: {source_file.name}

```
{source_content}
```
"""

    # Write prompt to temp file
    prompt_file = Path(tempfile.gettempdir()) / CONVERSION_PROMPT_FILE
    prompt_file.write_text(prompt, encoding="utf-8")

    # Output file location
    output_path = Path(tempfile.gettempdir()) / CONVERSION_OUTPUT_FILE
    stderr_file = Path(tempfile.gettempdir()) / f"{CONVERSION_OUTPUT_FILE}.err"

    # Build and execute Claude Code command
    try:
        cmd = [CLAUDE_CODE_CMD, "--print"]
        if use_modern_cli:
            cmd.extend(["--output-format", CLAUDE_OUTPUT_FORMAT])

        # Write prompt to stdin and capture output
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8"
        )

        # Write output
        output_path.write_text(result.stdout if result.stdout else "", encoding="utf-8")
        if result.stderr:
            stderr_file.write_text(result.stderr, encoding="utf-8")

        cli_exit_code = result.returncode

    except subprocess.TimeoutExpired:
        log("ERROR", "PRD conversion timed out")
        return False
    except Exception as e:
        log("ERROR", f"PRD conversion failed: {e}")
        return False

    # Log stderr if there was any
    if stderr_file.exists() and stderr_file.stat().st_size > 0:
        log("WARN", "CLI stderr output detected (see stderr file)")

    # Process the response
    if output_path.exists():
        output_format = detect_response_format(output_path)
        if output_format == "json":
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Check for errors in JSON response
                has_errors = data.get("metadata", {}).get("has_errors", False) or data.get("has_errors", False)
                if has_errors and data.get("metadata", {}).get("completion_status") == "failed":
                    log("ERROR", "PRD conversion failed")
                    error_msg = data.get("metadata", {}).get("error_message", "") or data.get("error_message", "")
                    if error_msg:
                        log("ERROR", f"Error: {error_msg}")
                    return False

                # Log result
                result_text = data.get("result") or data.get("summary", "")
                if result_text:
                    log("SUCCESS", f"PRD conversion completed: {result_text}")
                else:
                    log("SUCCESS", "PRD conversion completed")

            except json.JSONDecodeError:
                log("WARN", "Invalid JSON in output, conversion may have completed")
                log("SUCCESS", "PRD conversion completed")
        else:
            log("SUCCESS", "PRD conversion completed")

    # Clean up temp files
    for f in [prompt_file, output_path, stderr_file]:
        if f.exists():
            try:
                f.unlink()
            except Exception:
                pass

    if cli_exit_code != 0:
        log("ERROR", f"PRD conversion failed (exit code: {cli_exit_code})")
        return False

    # Verify files were created
    expected_files = [".ralph/PROMPT.md", ".ralph/fix_plan.md", ".ralph/specs/requirements.md"]
    missing = []
    for fname in expected_files:
        if not Path(fname).exists():
            missing.append(fname)

    if missing:
        log("WARN", f"Some files were not created: {', '.join(missing)}")
        log("INFO", "You may need to create these files manually or run the conversion again")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Ralph Import - Convert PRDs to Ralph Format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ralph_import.py my-app-prd.md
  ralph_import.py requirements.txt my-awesome-app
  ralph_import.py project-spec.json --output ./output-dir

Supported formats:
  - Markdown (.md)
  - Text files (.txt)
  - JSON (.json)
  - Any text-based format
        """
    )
    parser.add_argument(
        "prd_file",
        help="Path to your PRD/specification file"
    )
    parser.add_argument(
        "project_name",
        nargs="?",
        default=None,
        help="Name for the new Ralph project (optional, defaults to filename)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory for the project"
    )

    args = parser.parse_args()

    source_file = Path(args.prd_file)
    if not source_file.exists():
        log("ERROR", f"Source file does not exist: {source_file}")
        sys.exit(1)

    # Default project name from filename
    project_name = args.project_name
    if not project_name:
        project_name = source_file.stem

    log("INFO", f"Converting PRD: {source_file}")
    log("INFO", f"Project name: {project_name}")

    if not check_dependencies():
        sys.exit(1)

    # Import ralph_setup to use
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from ralph_setup import setup_project, find_templates_dir
    except ImportError:
        log("ERROR", "Could not import ralph_setup module")
        sys.exit(1)

    # Create project directory
    output_dir = args.output or Path.cwd()
    project_dir = output_dir / project_name

    log("INFO", f"Creating Ralph project: {project_name}")

    # Setup project
    templates_dir = find_templates_dir()
    if not templates_dir:
        log("ERROR", "Templates directory not found. Please run install.sh first.")
        sys.exit(1)

    setup_project(project_name, templates_dir)

    # Copy source file to project
    source_basename = source_file.name
    if source_file.is_absolute():
        shutil.copy2(source_file, project_dir / source_basename)
    else:
        shutil.copy2(source_file, project_dir / source_basename)

    # Change to project directory for conversion
    original_cwd = Path.cwd()
    os.chdir(project_dir)

    try:
        # Run conversion
        success = convert_prd(Path(source_basename), project_name)

        if success:
            log("SUCCESS", "PRD imported successfully!")
            print()
            print("Next steps:")
            print("  1. Review and edit the generated files:")
            print("     - .ralph/PROMPT.md (Ralph instructions)")
            print("     - .ralph/fix_plan.md (task priorities)")
            print("     - .ralph/specs/requirements.md (technical specs)")
            print("  2. Start autonomous development:")
            print("     ralph --monitor")
            print()
            print(f"Project created in: {project_dir}")
        else:
            log("ERROR", "PRD import failed")
            sys.exit(1)
    finally:
        os.chdir(original_cwd)


if __name__ == "__main__":
    main()

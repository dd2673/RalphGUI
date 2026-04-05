#!/usr/bin/env python3
"""
Ralph Import - Convert PRDs to Ralph format using Claude Code.

Version: 0.9.8 - Modern CLI support with JSON output parsing
"""

import os
import sys
import click
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import subprocess
import json
import tempfile
import re


# Configuration
CLAUDE_CODE_CMD = "claude"
CLAUDE_OUTPUT_FORMAT = "json"
CLAUDE_ALLOWED_TOOLS = ["Read", "Write", "Bash(mkdir:*)", "Bash(cp:*)"]
CLAUDE_MIN_VERSION = "2.0.76"

# Colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'


def log(level: str, message: str) -> None:
    """Log a message with level."""
    colors = {
        "INFO": BLUE,
        "WARN": YELLOW,
        "ERROR": RED,
        "SUCCESS": GREEN
    }
    color = colors.get(level, "")
    print(f"{color}[{level}]{NC} {message}")


# =============================================================================
# VERSION CHECKING
# =============================================================================

def check_claude_version() -> Tuple[bool, str]:
    """
    Verify Claude Code CLI version meets minimum requirements.

    Returns:
        Tuple of (success, version_string)
    """
    try:
        result = subprocess.run(
            [CLAUDE_CODE_CMD, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return False, ""

        # Extract version number
        match = re.search(r'(\d+\.\d+\.\d+)', result.stdout)
        if match:
            return True, match.group(1)
        return False, ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, ""


def compare_semver(v1: str, v2: str) -> int:
    """
    Compare two semantic version strings.

    Returns:
        -1 if v1 < v2, 0 if equal, 1 if v1 > v2
    """
    def parse_version(v: str) -> Tuple[int, int, int]:
        parts = v.split(".")
        return (
            int(parts[0]) if len(parts) > 0 else 0,
            int(parts[1]) if len(parts) > 1 else 0,
            int(parts[2]) if len(parts) > 2 else 0
        )

    major1, minor1, patch1 = parse_version(v1)
    major2, minor2, patch2 = parse_version(v2)

    if major1 < major2:
        return -1
    elif major1 > major2:
        return 1

    if minor1 < minor2:
        return -1
    elif minor1 > minor2:
        return 1

    if patch1 < patch2:
        return -1
    elif patch1 > patch2:
        return 1

    return 0


# =============================================================================
# JSON OUTPUT FORMAT DETECTION AND PARSING
# =============================================================================

def detect_response_format(output_file: Path) -> str:
    """
    Detect whether file contains JSON or plain text output.

    Returns:
        "json" if file is valid JSON, "text" otherwise
    """
    if not output_file.exists() or output_file.stat().st_size == 0:
        return "text"

    try:
        with open(output_file) as f:
            first_char = f.read(1)

        if first_char not in ("{", "["):
            return "text"

        # Validate as JSON
        with open(output_file) as f:
            json.load(f)
        return "json"
    except (json.JSONDecodeError, IOError):
        return "text"


def parse_conversion_response(output_file: Path) -> Dict[str, Any]:
    """
    Parse JSON response and extract conversion status.

    Returns:
        Dictionary with parsed fields
    """
    result = {
        "result": "",
        "session_id": "",
        "files_changed": 0,
        "has_errors": False,
        "completion_status": "unknown",
        "error_message": "",
        "error_code": "",
        "files_created": [],
        "missing_files": []
    }

    if not output_file.exists():
        return result

    try:
        with open(output_file) as f:
            data = json.load(f)

        # Extract fields - supports both flat format and Claude CLI format
        result["result"] = data.get("result", data.get("summary", ""))
        result["session_id"] = data.get("sessionId", data.get("session_id", ""))

        metadata = data.get("metadata", data)
        result["files_changed"] = metadata.get("files_changed", 0)
        result["has_errors"] = metadata.get("has_errors", False)
        result["completion_status"] = metadata.get("completion_status", "unknown")
        result["error_message"] = metadata.get("error_message", "")
        result["error_code"] = metadata.get("error_code", "")
        result["files_created"] = metadata.get("files_created", [])
        result["missing_files"] = metadata.get("missing_files", [])

    except (json.JSONDecodeError, IOError):
        pass

    return result


# =============================================================================
# CONVERSION
# =============================================================================

def create_conversion_prompt(source_file: Path) -> str:
    """Create the conversion prompt for Claude."""
    return """# PRD to Ralph Conversion Task

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

### 2. .ralph/fix_plan.md
Convert requirements into a prioritized task list with markdown checkbox format.

### 3. .ralph/specs/requirements.md
Create detailed technical specifications.

## Instructions
1. Read and analyze the attached specification file
2. Create the three files above with content derived from the PRD
3. Ensure all requirements are captured and properly prioritized
4. Make the PROMPT.md actionable for autonomous development
5. Structure fix_plan.md with clear, implementable tasks

"""


def convert_prd(
    source_file: Path,
    project_name: str,
    output_dir: Optional[Path] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Convert PRD using Claude Code.

    Returns:
        Tuple of (success, parsed_result)
    """
    if output_dir is None:
        output_dir = Path.cwd()

    log("INFO", "Converting PRD to Ralph format using Claude Code...")

    # Check Claude version
    version_ok, version = check_claude_version()
    use_modern_cli = version_ok and compare_semver(version, CLAUDE_MIN_VERSION) >= 0

    if use_modern_cli:
        log("INFO", "Using modern CLI with JSON output format")
    else:
        log("INFO", "Using standard CLI mode (modern features may not be available)")

    # Create conversion prompt
    prompt_content = create_conversion_prompt(source_file)

    # Append source content
    try:
        with open(source_file) as f:
            source_content = f.read()
        prompt_content += f"\n---\n\n## Source PRD File: {source_file.name}\n\n{source_content}"
    except IOError as e:
        log("ERROR", f"Failed to read source file: {e}")
        return False, {}

    # Create temp files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as pf:
        prompt_file = Path(pf.name)
        pf.write(prompt_content)

    output_file = output_dir / ".ralph_conversion_output.json"
    stderr_file = output_dir / ".ralph_conversion_output.err"

    try:
        # Build Claude command
        if use_modern_cli:
            cmd = [
                CLAUDE_CODE_CMD,
                "--print",
                "--strict-mcp-config",
                f"--output-format={CLAUDE_OUTPUT_FORMAT}",
                "--allowed-tools", ",".join(CLAUDE_ALLOWED_TOOLS)
            ]
        else:
            cmd = [CLAUDE_CODE_CMD, "--print"]

        # Execute
        result = subprocess.run(
            cmd,
            stdin=prompt_file.open(),
            stdout=open(output_file, 'w'),
            stderr=open(stderr_file, 'w'),
            timeout=300
        )
        cli_exit_code = result.returncode

        # Log stderr if there was any
        if stderr_file.exists() and stderr_file.stat().st_size > 0:
            log("WARN", "CLI stderr output detected")

        # Process response
        parsed_result = {}
        json_parsed = False

        if output_file.exists():
            output_format = detect_response_format(output_file)

            if output_format == "json":
                parsed_result = parse_conversion_response(output_file)
                json_parsed = True
                log("INFO", "Parsed JSON response from Claude CLI")

                if parsed_result["has_errors"] and parsed_result["completion_status"] == "failed":
                    log("ERROR", "PRD conversion failed")
                    if parsed_result["error_message"]:
                        log("ERROR", f"Error: {parsed_result['error_message']}")
                    if parsed_result["error_code"]:
                        log("ERROR", f"Error code: {parsed_result['error_code']}")
                    return False, parsed_result

                if parsed_result["session_id"]:
                    log("INFO", f"Session ID: {parsed_result['session_id']}")

                if parsed_result["files_changed"]:
                    log("INFO", f"Files changed: {parsed_result['files_changed']}")

        # Check CLI exit code
        if cli_exit_code != 0:
            log("ERROR", f"PRD conversion failed (exit code: {cli_exit_code})")
            return False, parsed_result

        # Success message
        if json_parsed and parsed_result.get("result"):
            log("SUCCESS", f"PRD conversion completed: {parsed_result['result']}")
        else:
            log("SUCCESS", "PRD conversion completed")

        return True, parsed_result

    except subprocess.TimeoutExpired:
        log("ERROR", "PRD conversion timed out")
        return False, {}
    except Exception as e:
        log("ERROR", f"PRD conversion failed: {e}")
        return False, {}
    finally:
        # Cleanup temp files
        if prompt_file.exists():
            prompt_file.unlink()
        if output_file.exists():
            output_file.unlink()
        if stderr_file.exists():
            stderr_file.unlink()


def verify_created_files(output_dir: Path, expected_files: List[str]) -> Tuple[List[str], List[str]]:
    """
    Verify that expected files were created.

    Returns:
        Tuple of (created_files, missing_files)
    """
    created = []
    missing = []

    for file in expected_files:
        if (output_dir / file).exists():
            created.append(file)
        else:
            missing.append(file)

    return created, missing


# =============================================================================
# CLI COMMAND
# =============================================================================

@click.command()
@click.argument("prd_file", type=click.Path(exists=True))
@click.argument("project_name", required=False)
@click.option("--output", "-o", default=".", help="Output directory")
def import_prd(prd_file: str, project_name: Optional[str], output: str = ".") -> None:
    """
    Convert PRD document to Ralph format.

    This command will:

    1. Create a new Ralph project

    2. Use Claude Code to intelligently convert your PRD into:
       - .ralph/PROMPT.md (Ralph instructions)
       - .ralph/fix_plan.md (prioritized tasks)
       - .ralph/specs/ (technical specifications)

    Examples:

        ralph-import my-app-prd.md

        ralph-import requirements.txt my-awesome-app

        ralph-import project-spec.json --output ./my-project
    """
    source_path = Path(prd_file).resolve()
    output_path = Path(output).resolve()

    # Default project name from filename
    if not project_name:
        project_name = source_path.stem

    log("INFO", f"Converting PRD: {source_path}")
    log("INFO", f"Project name: {project_name}")

    # Check dependencies
    try:
        subprocess.run([CLAUDE_CODE_CMD, "--version"], capture_output=True, timeout=10)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        log("WARN", f"Claude Code CLI ({CLAUDE_CODE_CMD}) not found. It will be downloaded when first used.")

    # Create project directory
    project_dir = output_path / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    log("INFO", f"Creating Ralph project: {project_name}")

    # Copy source file to project
    source_basename = source_path.name
    dest_source = project_dir / source_basename
    try:
        import shutil
        shutil.copy2(source_path, dest_source)
    except IOError as e:
        log("ERROR", f"Failed to copy source file: {e}")
        sys.exit(1)

    # Run conversion
    success, result = convert_prd(dest_source, project_name, project_dir)

    if not success:
        log("ERROR", "PRD conversion failed")
        sys.exit(1)

    # Verify files were created
    expected_files = [".ralph/PROMPT.md", ".ralph/fix_plan.md", ".ralph/specs/requirements.md"]
    created, missing = verify_created_files(project_dir, expected_files)

    if created:
        log("INFO", f"Created files: {', '.join(created)}")

    if missing:
        log("WARN", f"Some files were not created: {', '.join(missing)}")
        log("INFO", "You may need to create these files manually or run the conversion again")

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


if __name__ == "__main__":
    import_prd()
